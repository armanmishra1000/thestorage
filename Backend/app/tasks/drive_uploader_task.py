import asyncio
import os
import random
from pathlib import Path
import json

import httpx
from celery import Celery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus

# --- Configuration Constants ---
CHUNK_SIZE = 16 * 1024 * 1024  # 16MB

@celery_app.task(name="tasks.oauth_resumable_upload")
def oauth_resumable_upload(file_id: str, file_path_str: str, filename: str):
    """
    The definitive upload task. Uses OAuth 2.0 for authentication and a low-level
    resumable upload for data transfer to avoid all library conflicts.
    """
    file_path = Path(file_path_str)
    gdrive_id = None
    creds = None
    try:
        print(f"[CELERY_WORKER] Starting RESILIENT OAuth upload for {file_id}")

        # 1. AUTHENTICATION (OAuth 2.0 Refresh Token Flow)
        # This part is proven to work.
        with open(settings.GOOGLE_OAUTH_CREDENTIALS_PATH, 'r') as f:
            client_config = json.load(f)['installed']
        
        creds = Credentials(
            token=None,
            refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
            token_uri=client_config['token_uri'],
            client_id=client_config['client_id'],
            client_secret=client_config['client_secret'],
            scopes=['https://www.googleapis.com/auth/drive']
        )
        creds.refresh(Request())
        access_token = creds.token
        print("[CELERY_WORKER] OAuth token refreshed successfully.")
        
        # 2. INITIATE RESUMABLE UPLOAD
        # We will use httpx for this to get the session URL directly.
        total_size = os.path.getsize(file_path)
        metadata = {
            "name": filename,
            "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]
        }
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "application/octet-stream",
            "X-Upload-Content-Length": str(total_size)
        }
        
        print("[CELERY_WORKER] Initiating resumable upload session with Google...")
        async def initiate():
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
                    headers=headers,
                    json=metadata,
                )
                r.raise_for_status()
                return r.headers["Location"]
        
        upload_url = asyncio.run(initiate())
        print(f"[CELERY_WORKER] Resumable session created. URL: {upload_url[:50]}...")
        
        # 3. SEQUENTIAL CHUNK UPLOAD (using httpx)
        # This avoids all file lock issues.
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})
        
        print(f"[CELERY_WORKER] Starting chunked upload...")
        async def upload_chunks():
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    start = 0
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        
                        chunk_len = len(chunk)
                        end = start + chunk_len - 1
                        
                        headers = {
                            "Content-Length": str(chunk_len),
                            "Content-Range": f"bytes {start}-{end}/{total_size}"
                        }
                        
                        print(f"[UPLOADER] Sending chunk: {headers['Content-Range']}")
                        res = await client.put(upload_url, content=chunk, headers=headers, timeout=120.0)
                        
                        # A 200 or 201 means the upload is complete.
                        if res.status_code in [200, 201]:
                            print("[UPLOADER] Final chunk uploaded. Upload complete.")
                            return res.json()
                        
                        # A 308 means the chunk was received, continue to the next one.
                        elif res.status_code == 308:
                            pass
                        else:
                            # Any other status is an error.
                            res.raise_for_status()
                            
                        start += chunk_len

        final_response = asyncio.run(upload_chunks())
        gdrive_id = final_response.get('id')

        print(f"[CELERY_WORKER] Upload successful! GDrive ID: {gdrive_id}")

        # 4. FINALIZE DB
        db.files.update_one(
            {"_id": file_id},
            {"$set": {"status": UploadStatus.COMPLETED, "storage_location": "gdrive", "gdrive_id": gdrive_id}}
        )
        print(f"[CELERY_WORKER] Successfully finalized {file_id} in database.")

    except Exception as e:
        print(f"!!! [CELERY_WORKER] FINAL UPLOAD FAILED for {file_id}: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        # Note: In this resumable model, a placeholder is not created first,
        # so there's nothing to clean up in Drive on failure.
    finally:
        # 5. CLEANUP
        # This will now work because our task has full control over the file handle.
        if file_path.exists():
            file_path.unlink()
            print(f"[CELERY_WORKER] Cleaned up temp file: {file_path}")