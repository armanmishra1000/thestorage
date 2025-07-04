import os
import json
from pathlib import Path
from celery import chain
import httpx

# Import the correct Credentials class and AuthorizedSession
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession

from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus
from app.services import google_drive_service
from app.tasks.telegram_uploader_task import transfer_to_telegram
from app.progress_manager import ProgressManager
from app.models.file import UploadStatus, StorageLocation

CHUNKSIZE = 64 * 1024 * 1024

# @celery_app.task(name="tasks.finalize_and_delete")
# def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
#     try:
#         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
#         db.files.update_one(
#             {"_id": file_id},
#             {"$set": { "status": "completed", "storage_location": "telegram", "telegram_message_ids": telegram_message_ids }}
#         )
#         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

#         # --- START OF NEW CODE ---
#         # Announce that the file is ready for download via Redis Pub/Sub
#         progress = ProgressManager(file_id)
#         # We don't need to construct the full URL, just the path is enough.
#         # The frontend will build the full link.
#         download_path = f"/download/{file_id}" 
#         progress.publish_success(download_path)
#         print(f"[FINALIZER_TASK] Published success message for {file_id}.")
#         # --- END OF NEW CODE ---

#         google_drive_service.delete_file_with_refresh_token(gdrive_id)

#     except Exception as e:
#         # --- ADD ERROR PUBLISHING ---
#         progress = ProgressManager(file_id)
#         progress.publish_error(f"Failed during finalization: {e}")
#         # --- END OF CHANGE ---
#         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")

# # @celery_app.task(name="tasks.upload_to_drive")
# # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
#     """
#     The definitive upload task using manual, authorized HTTP requests to
#     guarantee that the user's OAuth credentials are used, bypassing any
#     environment variable conflicts.
#     """
#     file_path = Path(file_path_str)
#     gdrive_id = None
#     try:
#         print(f"[DRIVE_UPLOADER_MANUAL] Starting upload for {file_id} using manual OAuth 2.0.")
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

#         # 1. AUTHENTICATION: Build user credentials from the refresh token.
#         creds = Credentials.from_authorized_user_info(
#             info={
#                 "client_id": settings.OAUTH_CLIENT_ID,
#                 "client_secret": settings.OAUTH_CLIENT_SECRET,
#                 "refresh_token": settings.OAUTH_REFRESH_TOKEN,
#             },
#             scopes=['https://www.googleapis.com/auth/drive']
#         )
        
#         # 2. CREATE AN AUTHORIZED HTTP SESSION
#         # This session will automatically handle refreshing the access token for us.
#         authed_session = AuthorizedSession(creds)

#         # 3. INITIATE RESUMABLE UPLOAD (Manual HTTP POST)
#         file_size = os.path.getsize(file_path)
#         metadata = {
#             'name': filename,
#             'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
#         }
#         headers = {
#             'Content-Type': 'application/json; charset=UTF-8',
#             'X-Upload-Content-Type': 'application/octet-stream',
#             'X-Upload-Content-Length': str(file_size)
#         }
        
#         print("[DRIVE_UPLOADER_MANUAL] Initiating resumable session...")
#         init_response = authed_session.post(
#             'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable',
#             headers=headers,
#             data=json.dumps(metadata)
#         )
#         init_response.raise_for_status()
#         upload_url = init_response.headers['Location']
#         print("[DRIVE_UPLOADER_MANUAL] Session initiated successfully.")

#         # 4. UPLOAD FILE CONTENT (Manual HTTP PUT)
#         with open(file_path, 'rb') as f:
#             upload_response = authed_session.put(upload_url, data=f)
#             upload_response.raise_for_status()
#             response_data = upload_response.json()

#         gdrive_id = response_data.get('id')
#         if not gdrive_id:
#             raise Exception("Upload to Drive succeeded, but no file ID was returned.")

#         print(f"[DRIVE_UPLOADER_MANUAL] GDrive upload successful! GDrive ID: {gdrive_id}")

#         # 5. TASK CHAINING (This remains the same)
#         print(f"[DRIVE_UPLOADER_MANUAL] Creating task chain...")
#         task_chain = chain(
#                 # Pass file_id so the task can look up the filename
#                 transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
#                 finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
#             )
#         task_chain.delay()
#         print(f"[DRIVE_UPLOADER_MANUAL] Task chain dispatched.")

#     except Exception as e:
#         print(f"!!! [DRIVE_UPLOADER_MANUAL] Main task failed for {file_id}: {e}")
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
#         # We don't need to delete a placeholder since the upload will fail before one is created
#     finally:
#         if file_path.exists():
#             file_path.unlink()
#             print(f"[DRIVE_UPLOADER_MANUAL] Cleaned up temp file.")



# Backend/app/tasks/drive_uploader_task.py

import os
import json
from pathlib import Path
from celery import chain

# Import what we need
from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus, StorageLocation # <-- Import StorageLocation
from app.services import google_drive_service
from app.progress_manager import ProgressManager # <-- Import the ProgressManager
from app.tasks.telegram_uploader_task import transfer_to_telegram

# We no longer need the chain or the other tasks
# from celery import chain
# from app.tasks.telegram_uploader_task import transfer_to_telegram


# The old finalize_and_delete task is no longer needed, its logic is now in upload_to_drive_task
# @celery_app.task(name="tasks.finalize_and_delete")
# def finalize_and_delete(...)



@celery_app.task(name="tasks.upload_to_drive")
def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
    """
    This task now handles the entire process:
    1. Uploads the file from the server disk to Google Drive.
    2. Updates the database to mark the file as complete.
    3. Notifies the user of success.
    """
    file_path = Path(file_path_str)
    progress = ProgressManager(file_id) # Instantiate progress manager at the start

    try:
        print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

        # --- THIS PART IS THE SAME: UPLOAD TO GOOGLE DRIVE ---
        # (Using manual session for robustness, which is great)
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession

        creds = Credentials.from_authorized_user_info(
            info={
                "client_id": settings.OAUTH_CLIENT_ID,
                "client_secret": settings.OAUTH_CLIENT_SECRET,
                "refresh_token": settings.OAUTH_REFRESH_TOKEN,
            },
            scopes=['https://www.googleapis.com/auth/drive']
        )
        authed_session = AuthorizedSession(creds)
        file_size = os.path.getsize(file_path)
        metadata = { 'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID] }
        headers = { 'Content-Type': 'application/json; charset=UTF-8', 'X-Upload-Content-Type': 'application/octet-stream', 'X-Upload-Content-Length': str(file_size) }
        
        init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
        init_response.raise_for_status()
        upload_url = init_response.headers['Location']
        
        with open(file_path, 'rb') as f:
            upload_response = authed_session.put(upload_url, data=f)
            upload_response.raise_for_status()
            response_data = upload_response.json()

        gdrive_id = response_data.get('id')
        if not gdrive_id:
            raise Exception("Upload to Drive succeeded, but no file ID was returned.")

        print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

        # --- THIS IS THE NEW FINALIZATION LOGIC ---
        # 1. Update the database record to mark it as complete and stored in GDrive
        db.files.update_one(
            {"_id": file_id},
            {
                "$set": {
                    "status": UploadStatus.COMPLETED,
                    "storage_location": StorageLocation.GDRIVE, # Set storage to GDrive
                    "gdrive_id": gdrive_id # Save the ID
                }
            }
        )
        print(f"[GDRIVE_TASK] Database updated for {file_id}. Status: COMPLETED, Location: GDrive.")

        # 2. Announce success to the user via the progress WebSocket
        download_path = f"/download/{file_id}"
        progress.publish_success(download_path)
        print(f"[GDRIVE_TASK] Published success message for {file_id}.")

    except Exception as e:
        print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        # Announce the error to the user
        progress.publish_error(str(e))
    
    finally:
        # 3. Clean up the temporary file from the server disk
        if file_path.exists():
            file_path.unlink()
            print(f"[GDRIVE_TASK] Cleaned up temp file.")