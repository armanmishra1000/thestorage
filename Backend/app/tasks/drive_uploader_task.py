import asyncio
import httpx
import os
from pathlib import Path
from app.db.mongodb import db
from app.models.file import UploadStatus
from app.celery_worker import celery_app
from app.core.config import settings

# Import all necessary Google libraries directly into the task module
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

PARALLEL_CHUNK_SIZE_BYTES = 16 * 1024 * 1024 

async def upload_chunk(client: httpx.AsyncClient, upload_url: str, file_path: Path, start: int, size: int, total_size: int, access_token: str):
    end = start + size - 1
    headers = {
        'Content-Length': str(size),
        'Content-Range': f'bytes {start}-{end}/{total_size}',
        'Authorization': f'Bearer {access_token}'
    }
    # ... (The rest of this function is correct and does not need to change)
    print(f"[UPLOADER_TASK] Uploading chunk: {headers['Content-Range']}")
    with open(file_path, "rb") as f:
        f.seek(start)
        chunk_data = f.read(size)
    try:
        res = await client.put(upload_url, content=chunk_data, headers=headers, timeout=120)
        res.raise_for_status()
        print(f"[UPLOADER_TASK] Chunk {start}-{end} uploaded successfully.")
        return res
    except httpx.RequestError as e:
        print(f"[UPLOADER_TASK] An error occurred while uploading chunk {start}-{end}: {e}")
        raise

@celery_app.task(name="tasks.upload_to_drive")
def parallel_upload_to_drive(file_id: str, file_path_str: str, filename: str):
    file_path = Path(file_path_str)

    async def _run_upload():
        # --- THIS IS THE NEW, SELF-CONTAINED AUTH LOGIC ---
        gdrive_id = None # Define gdrive_id in a broader scope
        try:
            # 1. Create a fully-scoped credential object INSIDE the task.
            print("[CELERY_WORKER] Creating fully-scoped Google credentials...")
            SCOPES = ['https://www.googleapis.com/auth/drive']
            creds = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
            
            # 2. Create the placeholder file to get a gdrive_id
            service = build('drive', 'v3', credentials=creds)
            file_metadata = {
                'name': filename,
                'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
            }
            placeholder_file = service.files().create(body=file_metadata, fields='id').execute()
            gdrive_id = placeholder_file.get('id')
            if not gdrive_id:
                raise Exception("Failed to create placeholder file.")
            print(f"[CELERY_WORKER] Placeholder created with GDrive ID: {gdrive_id}")

            # 3. Initiate the resumable session using the same credentials
            from google.auth.transport.requests import AuthorizedSession
            authed_session = AuthorizedSession(creds)
            response = authed_session.patch(
                f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
                headers={"Content-Length": "0"}
            )
            response.raise_for_status()
            upload_url = response.headers['Location']
            print(f"[CELERY_WORKER] Resumable session created successfully.")

            # 4. Refresh the token to ensure it's fresh for httpx
            creds.refresh(Request())
            access_token = creds.token

            # --- END OF NEW AUTH LOGIC ---

            total_size = os.path.getsize(file_path)
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})
            
            tasks = []
            async with httpx.AsyncClient() as client:
                for start in range(0, total_size, PARALLEL_CHUNK_SIZE_BYTES):
                    chunk_size = min(PARALLEL_CHUNK_SIZE_BYTES, total_size - start)
                    task = asyncio.create_task(
                        upload_chunk(client, upload_url, file_path, start, chunk_size, total_size, access_token)
                    )
                    tasks.append(task)
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    raise result

            print(f"[CELERY_WORKER] All chunks for {file_id} uploaded successfully.")
            db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": UploadStatus.COMPLETED, "storage_location": "gdrive", "gdrive_id": gdrive_id}}
            )
            print(f"[CELERY_WORKER] Successfully finalized {file_id} in database.")

        except Exception as e:
            print(f"!!! [CELERY_WORKER] Upload failed for {file_id}: {e}")
            # If the upload fails, we should try to delete the empty placeholder file
            if gdrive_id:
                try:
                    print(f"[CELERY_WORKER] Upload failed. Deleting placeholder file {gdrive_id}...")
                    creds = service_account.Credentials.from_service_account_file(
                        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
                    service = build('drive', 'v3', credentials=creds)
                    service.files().delete(fileId=gdrive_id).execute()
                except Exception as del_e:
                    print(f"!!! [CELERY_WORKER] Failed to delete placeholder file: {del_e}")
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        finally:
            if file_path.exists():
                file_path.unlink()
                print(f"[CELERY_WORKER] Cleaned up temp file: {file_path}")

    asyncio.run(_run_upload())