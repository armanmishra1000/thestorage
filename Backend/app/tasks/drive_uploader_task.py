# server/backend/app/tasks/drive_uploader_task.py

import asyncio
from pathlib import Path
from app.db.mongodb import db
from app.models.file import UploadStatus
from app.celery_worker import celery_app
from app.core.config import settings

# Import our new uploader service
from app.services import parallel_uploader_service, google_drive_service

# Import Google libraries needed for auth
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

@celery_app.task(name="tasks.upload_to_drive")
def upload_drive_task(file_id: str, file_path_str: str, filename: str):
    """
    A clean Celery task that acts as a high-level orchestrator.
    """
    file_path = Path(file_path_str)
    gdrive_id = None

    try:
        print(f"[CELERY_WORKER] Starting task for {file_id}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

        # 1. Get Google credentials and a fresh token
        SCOPES = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
        creds.refresh(Request())
        access_token = creds.token
        print(f"[CELERY_WORKER] Acquired fresh access token.")

        # 2. Get the resumable upload session
        gdrive_id, upload_url = google_drive_service.create_resumable_upload_session(filename, creds)
        
        # 3. Delegate the heavy lifting to the uploader service
        # We run the async service function in its own event loop.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                parallel_uploader_service.run_parallel_upload(upload_url, file_path, access_token)
            )
        finally:
            loop.close()
            
        # 4. Finalize in DB
        db.files.update_one(
            {"_id": file_id},
            {"$set": {"status": UploadStatus.COMPLETED, "storage_location": "gdrive", "gdrive_id": gdrive_id}}
        )
        print(f"[CELERY_WORKER] Task for {file_id} completed successfully.")

    except Exception as e:
        print(f"!!! [CELERY_WORKER] Task for {file_id} failed: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        # Cleanup placeholder file in Drive if it was created
        if gdrive_id:
            try:
                SCOPES = ['https://www.googleapis.com/auth/drive']
                creds = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
                service = build('drive', 'v3', credentials=creds)
                print(f"[CELERY_WORKER] Deleting failed placeholder file {gdrive_id}...")
                service.files().delete(fileId=gdrive_id).execute()
            except Exception as del_e:
                print(f"!!! [CELERY_WORKER] Could not delete placeholder file: {del_e}")
    finally:
        # Final cleanup of the local temp file
        if file_path.exists():
            file_path.unlink()
            print(f"[CELERY_WORKER] Cleaned up temp file: {file_path}")