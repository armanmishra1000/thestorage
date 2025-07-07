# # # # # # # import os
# # # # # # # import json
# # # # # # # from pathlib import Path
# # # # # # # from celery import chain
# # # # # # # import httpx

# # # # # # # # Import the correct Credentials class and AuthorizedSession
# # # # # # # from google.oauth2.credentials import Credentials
# # # # # # # from google.auth.transport.requests import AuthorizedSession

# # # # # # # from app.celery_worker import celery_app
# # # # # # # from app.core.config import settings
# # # # # # # from app.db.mongodb import db
# # # # # # # from app.models.file import UploadStatus
# # # # # # # from app.services import google_drive_service
# # # # # # # from app.tasks.telegram_uploader_task import transfer_to_telegram
# # # # # # # from app.progress_manager import ProgressManager
# # # # # # # from app.models.file import UploadStatus, StorageLocation

# # # # # # # CHUNKSIZE = 64 * 1024 * 1024

# # # # # # # # @celery_app.task(name="tasks.finalize_and_delete")
# # # # # # # # def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
# # # # # # # #     try:
# # # # # # # #         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
# # # # # # # #         db.files.update_one(
# # # # # # # #             {"_id": file_id},
# # # # # # # #             {"$set": { "status": "completed", "storage_location": "telegram", "telegram_message_ids": telegram_message_ids }}
# # # # # # # #         )
# # # # # # # #         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

# # # # # # # #         # --- START OF NEW CODE ---
# # # # # # # #         # Announce that the file is ready for download via Redis Pub/Sub
# # # # # # # #         progress = ProgressManager(file_id)
# # # # # # # #         # We don't need to construct the full URL, just the path is enough.
# # # # # # # #         # The frontend will build the full link.
# # # # # # # #         download_path = f"/download/{file_id}" 
# # # # # # # #         progress.publish_success(download_path)
# # # # # # # #         print(f"[FINALIZER_TASK] Published success message for {file_id}.")
# # # # # # # #         # --- END OF NEW CODE ---

# # # # # # # #         google_drive_service.delete_file_with_refresh_token(gdrive_id)

# # # # # # # #     except Exception as e:
# # # # # # # #         # --- ADD ERROR PUBLISHING ---
# # # # # # # #         progress = ProgressManager(file_id)
# # # # # # # #         progress.publish_error(f"Failed during finalization: {e}")
# # # # # # # #         # --- END OF CHANGE ---
# # # # # # # #         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")

# # # # # # # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # # # # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # # # # # #     """
# # # # # # # #     The definitive upload task using manual, authorized HTTP requests to
# # # # # # # #     guarantee that the user's OAuth credentials are used, bypassing any
# # # # # # # #     environment variable conflicts.
# # # # # # # #     """
# # # # # # # #     file_path = Path(file_path_str)
# # # # # # # #     gdrive_id = None
# # # # # # # #     try:
# # # # # # # #         print(f"[DRIVE_UPLOADER_MANUAL] Starting upload for {file_id} using manual OAuth 2.0.")
# # # # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # # # # # #         # 1. AUTHENTICATION: Build user credentials from the refresh token.
# # # # # # # #         creds = Credentials.from_authorized_user_info(
# # # # # # # #             info={
# # # # # # # #                 "client_id": settings.OAUTH_CLIENT_ID,
# # # # # # # #                 "client_secret": settings.OAUTH_CLIENT_SECRET,
# # # # # # # #                 "refresh_token": settings.OAUTH_REFRESH_TOKEN,
# # # # # # # #             },
# # # # # # # #             scopes=['https://www.googleapis.com/auth/drive']
# # # # # # # #         )
        
# # # # # # # #         # 2. CREATE AN AUTHORIZED HTTP SESSION
# # # # # # # #         # This session will automatically handle refreshing the access token for us.
# # # # # # # #         authed_session = AuthorizedSession(creds)

# # # # # # # #         # 3. INITIATE RESUMABLE UPLOAD (Manual HTTP POST)
# # # # # # # #         file_size = os.path.getsize(file_path)
# # # # # # # #         metadata = {
# # # # # # # #             'name': filename,
# # # # # # # #             'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
# # # # # # # #         }
# # # # # # # #         headers = {
# # # # # # # #             'Content-Type': 'application/json; charset=UTF-8',
# # # # # # # #             'X-Upload-Content-Type': 'application/octet-stream',
# # # # # # # #             'X-Upload-Content-Length': str(file_size)
# # # # # # # #         }
        
# # # # # # # #         print("[DRIVE_UPLOADER_MANUAL] Initiating resumable session...")
# # # # # # # #         init_response = authed_session.post(
# # # # # # # #             'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable',
# # # # # # # #             headers=headers,
# # # # # # # #             data=json.dumps(metadata)
# # # # # # # #         )
# # # # # # # #         init_response.raise_for_status()
# # # # # # # #         upload_url = init_response.headers['Location']
# # # # # # # #         print("[DRIVE_UPLOADER_MANUAL] Session initiated successfully.")

# # # # # # # #         # 4. UPLOAD FILE CONTENT (Manual HTTP PUT)
# # # # # # # #         with open(file_path, 'rb') as f:
# # # # # # # #             upload_response = authed_session.put(upload_url, data=f)
# # # # # # # #             upload_response.raise_for_status()
# # # # # # # #             response_data = upload_response.json()

# # # # # # # #         gdrive_id = response_data.get('id')
# # # # # # # #         if not gdrive_id:
# # # # # # # #             raise Exception("Upload to Drive succeeded, but no file ID was returned.")

# # # # # # # #         print(f"[DRIVE_UPLOADER_MANUAL] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # # # # # #         # 5. TASK CHAINING (This remains the same)
# # # # # # # #         print(f"[DRIVE_UPLOADER_MANUAL] Creating task chain...")
# # # # # # # #         task_chain = chain(
# # # # # # # #                 # Pass file_id so the task can look up the filename
# # # # # # # #                 transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # # # # # # #                 finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# # # # # # # #             )
# # # # # # # #         task_chain.delay()
# # # # # # # #         print(f"[DRIVE_UPLOADER_MANUAL] Task chain dispatched.")

# # # # # # # #     except Exception as e:
# # # # # # # #         print(f"!!! [DRIVE_UPLOADER_MANUAL] Main task failed for {file_id}: {e}")
# # # # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # # # # # #         # We don't need to delete a placeholder since the upload will fail before one is created
# # # # # # # #     finally:
# # # # # # # #         if file_path.exists():
# # # # # # # #             file_path.unlink()
# # # # # # # #             print(f"[DRIVE_UPLOADER_MANUAL] Cleaned up temp file.")



# # # # # # # # Backend/app/tasks/drive_uploader_task.py

# # # # # # # import os
# # # # # # # import json
# # # # # # # from pathlib import Path
# # # # # # # from celery import chain
# # # # # # # import math

# # # # # # # # Import what we need
# # # # # # # from app.celery_worker import celery_app
# # # # # # # from app.core.config import settings
# # # # # # # from app.db.mongodb import db
# # # # # # # from app.models.file import UploadStatus, StorageLocation # <-- Import StorageLocation
# # # # # # # from app.services import google_drive_service
# # # # # # # from app.progress_manager import ProgressManager # <-- Import the ProgressManager
# # # # # # # from app.tasks.telegram_uploader_task import transfer_to_telegram

# # # # # # # # We no longer need the chain or the other tasks
# # # # # # # # from celery import chain
# # # # # # # # from app.tasks.telegram_uploader_task import transfer_to_telegram

# # # # # # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024 

# # # # # # # # The old finalize_and_delete task is no longer needed, its logic is now in upload_to_drive_task
# # # # # # # # @celery_app.task(name="tasks.finalize_and_delete")
# # # # # # # # def finalize_and_delete(...)



# # # # # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # # # # #     """
# # # # # # #     This task now handles the entire process and reports progress:
# # # # # # #     1. Uploads the file from the server disk to Google Drive in chunks.
# # # # # # #     2. After each chunk, it publishes the progress percentage.
# # # # # # #     3. Updates the database to mark the file as complete.
# # # # # # #     4. Notifies the user of success.
# # # # # # #     """
# # # # # # #     file_path = Path(file_path_str)
# # # # # # #     progress = ProgressManager(file_id)

# # # # # # #     try:
# # # # # # #         print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
# # # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # # # # #         # --- SESSION AND AUTH (Unchanged) ---
# # # # # # #         from google.oauth2.credentials import Credentials
# # # # # # #         from google.auth.transport.requests import AuthorizedSession
# # # # # # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # # # # # #         authed_session = AuthorizedSession(creds)
        
# # # # # # #         # --- INITIATE RESUMABLE UPLOAD (Unchanged) ---
# # # # # # #         total_size = os.path.getsize(file_path)
# # # # # # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # # # # # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # # # # # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # # # # # #         init_response.raise_for_status()
# # # # # # #         upload_url = init_response.headers['Location']

# # # # # # #         # --- NEW CHUNKED UPLOAD LOGIC ---
# # # # # # #         bytes_sent = 0
# # # # # # #         with open(file_path, 'rb') as f:
# # # # # # #             while True:
# # # # # # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # # # # # #                 if not chunk:
# # # # # # #                     break # We are done

# # # # # # #                 start_byte = bytes_sent
# # # # # # #                 end_byte = bytes_sent + len(chunk) - 1
                
# # # # # # #                 # Construct the Content-Range header
# # # # # # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
                
# # # # # # #                 # Send the chunk
# # # # # # #                 upload_response = authed_session.put(
# # # # # # #                     upload_url,
# # # # # # #                     headers={'Content-Range': content_range},
# # # # # # #                     data=chunk
# # # # # # #                 )
# # # # # # #                 upload_response.raise_for_status()
                
# # # # # # #                 bytes_sent += len(chunk)

# # # # # # #                 # --- PUBLISH PROGRESS ---
# # # # # # #                 percentage = math.floor((bytes_sent / total_size) * 100)
# # # # # # #                 progress.publish_progress(percentage)
# # # # # # #                 print(f"[GDRIVE_TASK] Uploaded {bytes_sent}/{total_size} bytes ({percentage}%) for file {file_id}")

# # # # # # #         # The last response from Google contains the file ID
# # # # # # #         response_data = upload_response.json()
# # # # # # #         gdrive_id = response_data.get('id')
# # # # # # #         if not gdrive_id:
# # # # # # #             raise Exception("Upload to Drive finished, but no file ID was returned.")

# # # # # # #         print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # # # # #         # --- FINALIZATION LOGIC (Unchanged) ---
# # # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.COMPLETED, "storage_location": StorageLocation.GDRIVE, "gdrive_id": gdrive_id}})
# # # # # # #         print(f"[GDRIVE_TASK] Database updated for {file_id}. Status: COMPLETED, Location: GDrive.")
        
# # # # # # #         download_path = f"/download/{file_id}"
# # # # # # #         progress.publish_success(download_path)
# # # # # # #         print(f"[GDRIVE_TASK] Published success message for {file_id}.")

# # # # # # #     except Exception as e:
# # # # # # #         print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
# # # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # # # # #         progress.publish_error(str(e))
    
# # # # # # #     finally:
# # # # # # #         if file_path.exists():
# # # # # # #             file_path.unlink()
# # # # # # #             print(f"[GDRIVE_TASK] Cleaned up temp file.")



# # # # # # # Backend/app/tasks/drive_uploader_task.py

# # # # # # import os
# # # # # # import json
# # # # # # from pathlib import Path
# # # # # # import math

# # # # # # # --- Re-import the chain function ---
# # # # # # from celery import chain

# # # # # # # Import all our necessary components
# # # # # # from app.celery_worker import celery_app
# # # # # # from app.core.config import settings
# # # # # # from app.db.mongodb import db
# # # # # # from app.models.file import UploadStatus, StorageLocation
# # # # # # from app.services import google_drive_service
# # # # # # from app.progress_manager import ProgressManager

# # # # # # # --- Re-import the tasks that will be part of our chain ---
# # # # # # from app.tasks.telegram_uploader_task import transfer_to_telegram

# # # # # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

# # # # # # # --- This is the FINAL task in our chain ---
# # # # # # # It runs after the Telegram upload is successful.
# # # # # # @celery_app.task(name="tasks.finalize_and_delete")
# # # # # # def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
# # # # # #     """
# # # # # #     This task is the last step. It:
# # # # # #     1. Updates the DB to mark the file as completed and stored in Telegram.
# # # # # #     2. Notifies the user of success.
# # # # # #     3. Deletes the temporary file from Google Drive.
# # # # # #     """
# # # # # #     progress = ProgressManager(file_id)
# # # # # #     try:
# # # # # #         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
# # # # # #         db.files.update_one(
# # # # # #             {"_id": file_id},
# # # # # #             {
# # # # # #                 "$set": {
# # # # # #                     "status": UploadStatus.COMPLETED,
# # # # # #                     "storage_location": StorageLocation.TELEGRAM, # Set storage to Telegram
# # # # # #                     "telegram_message_ids": telegram_message_ids
# # # # # #                 }
# # # # # #             }
# # # # # #         )
# # # # # #         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

# # # # # #         # Announce success to the user
# # # # # #         download_path = f"/download/{file_id}"
# # # # # #         progress.publish_success(download_path)
# # # # # #         print(f"[FINALIZER_TASK] Published success message for {file_id}.")

# # # # # #         # Clean up the file from Google Drive
# # # # # #         google_drive_service.delete_file_with_refresh_token(gdrive_id)

# # # # # #     except Exception as e:
# # # # # #         progress.publish_error(f"Failed during finalization: {e}")
# # # # # #         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")

# # # # # # # --- This is the FIRST task in our chain ---
# # # # # # # It uploads to Google Drive and then starts the chain.
# # # # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # # # #     """
# # # # # #     This task now only does two things:
# # # # # #     1. Uploads the file to Google Drive while reporting progress.
# # # # # #     2. Kicks off the rest of the task chain.
# # # # # #     """
# # # # # #     file_path = Path(file_path_str)
# # # # # #     progress = ProgressManager(file_id)
# # # # # #     gdrive_id = None # Define gdrive_id here to use it in the chain

# # # # # #     try:
# # # # # #         print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
# # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # # # #         # (The chunked upload logic is the same)
# # # # # #         from google.oauth2.credentials import Credentials
# # # # # #         from google.auth.transport.requests import AuthorizedSession
# # # # # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # # # # #         authed_session = AuthorizedSession(creds)
# # # # # #         total_size = os.path.getsize(file_path)
# # # # # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # # # # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # # # # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # # # # #         init_response.raise_for_status()
# # # # # #         upload_url = init_response.headers['Location']

# # # # # #         bytes_sent = 0
# # # # # #         with open(file_path, 'rb') as f:
# # # # # #             while True:
# # # # # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # # # # #                 if not chunk:
# # # # # #                     break
# # # # # #                 start_byte = bytes_sent
# # # # # #                 end_byte = bytes_sent + len(chunk) - 1
# # # # # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
# # # # # #                 upload_response = authed_session.put(upload_url, headers={'Content-Range': content_range}, data=chunk)
# # # # # #                 upload_response.raise_for_status()
# # # # # #                 bytes_sent += len(chunk)
# # # # # #                 percentage = math.floor((bytes_sent / total_size) * 100)
# # # # # #                 progress.publish_progress(percentage)
# # # # # #                 print(f"[GDRIVE_TASK] Uploaded {bytes_sent}/{total_size} bytes ({percentage}%) for file {file_id}")
        
# # # # # #         response_data = upload_response.json()
# # # # # #         gdrive_id = response_data.get('id')
# # # # # #         if not gdrive_id:
# # # # # #             raise Exception("Upload to Drive finished, but no file ID was returned.")
        
# # # # # #         print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # # # #         # --- THIS IS THE RESTORED TASK CHAIN ---
# # # # # #         print(f"[GDRIVE_TASK] Creating and dispatching task chain...")
# # # # # #         # Create a chain of tasks:
# # # # # #         # 1. Transfer the file from GDrive to Telegram.
# # # # # #         # 2. Finalize by updating the DB and deleting from GDrive.
# # # # # #         task_chain = chain(
# # # # # #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # # # # #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# # # # # #         )
# # # # # #         task_chain.delay()
# # # # # #         print(f"[GDRIVE_TASK] Task chain dispatched successfully.")

# # # # # #     except Exception as e:
# # # # # #         print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
# # # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # # # #         progress.publish_error(str(e))
    
# # # # # #     finally:
# # # # # #         if file_path.exists():
# # # # # #             file_path.unlink()
# # # # # #             print(f"[GDRIVE_TASK] Cleaned up temp file.")



# # # # # # Backend/app/tasks/drive_uploader_task.py

# # # # # import os
# # # # # import json
# # # # # from pathlib import Path
# # # # # import math

# # # # # # --- Re-import the chain function ---
# # # # # from celery import chain

# # # # # # Import all our necessary components
# # # # # from app.celery_worker import celery_app
# # # # # from app.core.config import settings
# # # # # from app.db.mongodb import db
# # # # # from app.models.file import UploadStatus, StorageLocation
# # # # # from app.services import google_drive_service
# # # # # from app.progress_manager import ProgressManager

# # # # # # --- Re-import the tasks that will be part of our chain ---
# # # # # from app.tasks.telegram_uploader_task import transfer_to_telegram

# # # # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024  # 4MB

# # # # # # --- This is the FINAL task in our chain ---
# # # # # # It runs after the Telegram upload is successful.
# # # # # @celery_app.task(name="tasks.finalize_and_delete")
# # # # # def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
# # # # #     """
# # # # #     This task is the last step. It:
# # # # #     1. Updates the DB to mark the file as completed and stored in Telegram.
# # # # #     2. Notifies the user of success.
# # # # #     3. Deletes the temporary file from Google Drive.
# # # # #     """
# # # # #     progress = ProgressManager(file_id)
# # # # #     try:
# # # # #         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
# # # # #         db.files.update_one(
# # # # #             {"_id": file_id},
# # # # #             {
# # # # #                 "$set": {
# # # # #                     "status": UploadStatus.COMPLETED,
# # # # #                     "storage_location": StorageLocation.TELEGRAM, # Set storage to Telegram
# # # # #                     "telegram_message_ids": telegram_message_ids
# # # # #                 },
# # # # #                 # Unset gdrive_id as it's no longer the primary location
# # # # #                 "$unset": {"gdrive_id": ""}
# # # # #             }
# # # # #         )
# # # # #         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

# # # # #         # Announce success to the user
# # # # #         download_path = f"/download/{file_id}"
# # # # #         progress.publish_success(download_path)
# # # # #         print(f"[FINALIZER_TASK] Published success message for {file_id}.")

# # # # #         # Clean up the file from Google Drive
# # # # #         google_drive_service.delete_file_with_refresh_token(gdrive_id)

# # # # #     except Exception as e:
# # # # #         progress.publish_error(f"Failed during finalization: {e}")
# # # # #         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")

# # # # # # --- This is the FIRST task in our chain ---
# # # # # # It uploads to Google Drive and then starts the chain.
# # # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # # #     """
# # # # #     This task now only does two things:
# # # # #     1. Uploads the file to Google Drive while reporting progress.
# # # # #     2. Kicks off the rest of the task chain.
# # # # #     """
# # # # #     file_path = Path(file_path_str)
# # # # #     progress = ProgressManager(file_id)
# # # # #     gdrive_id = None # Define gdrive_id here to use it in the chain

# # # # #     try:
# # # # #         print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
# # # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # # #         from google.oauth2.credentials import Credentials
# # # # #         from google.auth.transport.requests import AuthorizedSession
# # # # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # # # #         authed_session = AuthorizedSession(creds)
# # # # #         total_size = os.path.getsize(file_path)
# # # # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # # # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # # # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # # # #         init_response.raise_for_status()
# # # # #         upload_url = init_response.headers['Location']

# # # # #         bytes_sent = 0
# # # # #         with open(file_path, 'rb') as f:
# # # # #             while True:
# # # # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # # # #                 if not chunk:
# # # # #                     break
# # # # #                 start_byte = bytes_sent
# # # # #                 end_byte = bytes_sent + len(chunk) - 1
# # # # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
# # # # #                 upload_response = authed_session.put(upload_url, headers={'Content-Range': content_range}, data=chunk)
# # # # #                 upload_response.raise_for_status()
# # # # #                 bytes_sent += len(chunk)
# # # # #                 percentage = math.floor((bytes_sent / total_size) * 100)
# # # # #                 # We only want to show progress for the Server -> Drive part, so we cap it at 99%
# # # # #                 # The final 100% and success signal comes from the finalizer task.
# # # # #                 if percentage < 100:
# # # # #                     progress.publish_progress(percentage)
# # # # #                 print(f"[GDRIVE_TASK] Uploaded {bytes_sent}/{total_size} bytes ({percentage}%) for file {file_id}")
        
# # # # #         response_data = upload_response.json()
# # # # #         gdrive_id = response_data.get('id')
# # # # #         if not gdrive_id:
# # # # #             raise Exception("Upload to Drive finished, but no file ID was returned.")
        
# # # # #         print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # # #         # Update DB to store the gdrive_id for the next task
# # # # #         db.files.update_one({"_id": file_id}, {"$set": {"gdrive_id": gdrive_id, "status": UploadStatus.TRANSFERRING_TO_TELEGRAM}})
        
# # # # #         # --- THIS IS THE RESTORED TASK CHAIN ---
# # # # #         print(f"[GDRIVE_TASK] Creating and dispatching task chain...")
# # # # #         # Create a chain of tasks:
# # # # #         # 1. Transfer the file from GDrive to Telegram.
# # # # #         # 2. Finalize by updating the DB and deleting from GDrive.
# # # # #         task_chain = chain(
# # # # #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # # # #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# # # # #         )
# # # # #         task_chain.delay()
# # # # #         print(f"[GDRIVE_TASK] Task chain dispatched successfully.")

# # #     # # except Exception as e:
# # #     # #     print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
# # #     # #     db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # #     # #     progress.publish_error(str(e))
    
# # #     # # finally:
# # #     # #     if file_path.exists():
# # #     # #         file_path.unlink()
# # #     #         print(f"[GDRIVE_TASK] Cleaned up temp file.")


# # # # # Backend/app/tasks/drive_uploader_task.py

# # # # import os
# # # # import json
# # # # from pathlib import Path
# # # # import math
# # # # from celery import chain

# # # # from app.celery_worker import celery_app
# # # # from app.core.config import settings
# # # # from app.db.mongodb import db
# # # # from app.models.file import UploadStatus, StorageLocation
# # # # from app.services import google_drive_service
# # # # from app.progress_manager import ProgressManager

# # # # # --- IMPORT THE TASKS FROM THEIR CORRECT MODULES ---
# # # # from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# # # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024

# # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # #     """
# # # #     This task uploads the file to Google Drive and then kicks off the task chain.
# # # #     """
# # # #     file_path = Path(file_path_str)
# # # #     progress = ProgressManager(file_id)
# # # #     gdrive_id = None

# # # #     try:
# # # #         print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
# # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # #         # (Authentication and Resumable Session logic is unchanged)
# # # #         from google.oauth2.credentials import Credentials
# # # #         from google.auth.transport.requests import AuthorizedSession
# # # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # # #         authed_session = AuthorizedSession(creds)
# # # #         total_size = os.path.getsize(file_path)
# # # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # # #         init_response.raise_for_status()
# # # #         upload_url = init_response.headers['Location']

# # # #         # (Chunked Upload and Progress Reporting logic is unchanged)
# # # #         bytes_sent = 0
# # # #         with open(file_path, 'rb') as f:
# # # #             while True:
# # # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # # #                 if not chunk: break
# # # #                 start_byte, end_byte = bytes_sent, bytes_sent + len(chunk) - 1
# # # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
# # # #                 upload_response = authed_session.put(upload_url, headers={'Content-Range': content_range}, data=chunk)
# # # #                 upload_response.raise_for_status()
# # # #                 bytes_sent += len(chunk)
# # # #                 percentage = math.floor((bytes_sent / total_size) * 100)
# # # #                 if percentage < 100:
# # # #                     progress.publish_progress(percentage)
# # # #                 print(f"[GDRIVE_TASK] Uploaded {bytes_sent}/{total_size} bytes ({percentage}%) for file {file_id}")
        
# # # #         response_data = upload_response.json()
# # # #         gdrive_id = response_data.get('id')
# # # #         if not gdrive_id:
# # # #             raise Exception("Upload to Drive finished, but no file ID was returned.")
        
# # # #         print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # #         db.files.update_one({"_id": file_id}, {"$set": {"gdrive_id": gdrive_id, "status": UploadStatus.TRANSFERRING_TO_TELEGRAM}})
        
# # # #         # --- THE TASK CHAIN (Now Correct) ---
# # # #         print(f"[GDRIVE_TASK] Creating and dispatching task chain...")
# # # #         task_chain = chain(
# # # #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # # #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id) # The signature for the final task
# # # #         )
# # # #         task_chain.delay()
# # # #         print(f"[GDRIVE_TASK] Task chain dispatched successfully.")

# # # #     except Exception as e:
# # # #         print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
# # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # #         progress.publish_error(str(e))
    
# # # #     finally:
# # # #         if file_path.exists():
# # # #             file_path.unlink()
# # # #             print(f"[GDRIVE_TASK] Cleaned up temp file.")





# # # # import os
# # # # import json
# # # # from pathlib import Path
# # # # import math
# # # # from celery import chain

# # # # from app.celery_worker import celery_app
# # # # from app.core.config import settings
# # # # from app.db.mongodb import db
# # # # from app.models.file import UploadStatus, StorageLocation
# # # # from app.services import google_drive_service
# # # # from app.progress_manager import ProgressManager
# # # # from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# # # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024

# # # # @celery_app.task(name="tasks.upload_to_drive")
# # # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # # #     """
# # # #     This task now:
# # # #     1. Uploads to GDrive while reporting progress.
# # # #     2. IMMEDIATELY sends the success signal to the user.
# # # #     3. Kicks off the silent background chain for Telegram transfer.
# # # #     """
# # # #     file_path = Path(file_path_str)
# # # #     progress = ProgressManager(file_id)
# # # #     gdrive_id = None

# # # #     try:
        
# # # #         print(f"[GDRIVE_TASK] Starting upload for file_id: {file_id}")
# # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # # #         from google.oauth2.credentials import Credentials
# # # #         from google.auth.transport.requests import AuthorizedSession
# # # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # # #         authed_session = AuthorizedSession(creds)
# # # #         total_size = os.path.getsize(file_path)
# # # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # # #         init_response.raise_for_status()
# # # #         upload_url = init_response.headers['Location']

# # # #         bytes_sent = 0
# # # #         with open(file_path, 'rb') as f:
# # # #             while True:
# # # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # # #                 if not chunk: break
# # # #                 start_byte, end_byte = bytes_sent, bytes_sent + len(chunk) - 1
# # # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
# # # #                 upload_response = authed_session.put(upload_url, headers={'Content-Range': content_range}, data=chunk)
# # # #                 upload_response.raise_for_status()
# # # #                 bytes_sent += len(chunk)
# # # #                 percentage = math.floor((bytes_sent / total_size) * 100)
# # # #                 progress.publish_progress(percentage)
# # # #                 print(f"[GDRIVE_TASK] Uploaded {bytes_sent}/{total_size} bytes ({percentage}%) for file {file_id}")
        
# # # #         response_data = upload_response.json()
# # # #         gdrive_id = response_data.get('id')
# # # #         if not gdrive_id:
# # # #             raise Exception("Upload to Drive finished, but no file ID was returned.")
        
# # # #         print(f"[GDRIVE_TASK] GDrive upload successful! GDrive ID: {gdrive_id}")

# # # #         # --- THIS IS THE KEY UX CHANGE ---
# # # #         # 1. Update the DB with GDrive info. We'll mark it COMPLETED for the user,
# # # #         #    even though the backend will continue working.
# # # #         db.files.update_one(
# # # #             {"_id": file_id},
# # # #             {"$set": {
# # # #                 "gdrive_id": gdrive_id,
# # # #                 "status": UploadStatus.COMPLETED,
# # # #                 "storage_location": StorageLocation.GDRIVE # Initial location is GDrive
# # # #             }}
# # # #         )
        
# # # #         # 2. Announce success to the user immediately.
# # # #         download_path = f"/download/{file_id}"
# # # #         progress.publish_success(download_path)
# # # #         print(f"[GDRIVE_TASK] Published user-facing success message for {file_id}.")

# # # #         # --- KICK OFF THE SILENT BACKGROUND TASK ---
# # # #         print(f"[GDRIVE_TASK] Dispatching silent background chain for Telegram transfer...")
# # # #         task_chain = chain(
# # # #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # # #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# # # #         )
# # # #         task_chain.delay()
# # # #         print(f"[GDRIVE_TASK] Task chain dispatched successfully.")

# # # #     except Exception as e:
# # # #         print(f"!!! [GDRIVE_TASK] Main task failed for {file_id}: {e}")
# # # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # #         progress.publish_error(str(e))
    
# # # #     finally:
# # # #         if file_path.exists():
# # # #             file_path.unlink()
# # # #             print(f"[GDRIVE_TASK] Cleaned up temp file.")


# # # #  Backend/app/tasks/drive_uploader_task.py

# # # import os
# # # import json
# # # from pathlib import Path
# # # import math
# # # from celery import chain

# # # from app.celery_worker import celery_app
# # # from app.core.config import settings
# # # from app.db.mongodb import db
# # # from app.models.file import UploadStatus, StorageLocation
# # # from app.services import google_drive_service
# # # from app.progress_manager import ProgressManager
# # # from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# # # DRIVE_CHUNK_SIZE = 4 * 1024 * 1024

# # # @celery_app.task(name="tasks.upload_to_drive")
# # # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# # #     """
# # #     This task:
# # #     1. Uploads the file from server temp storage to Google Drive, reporting progress via Redis.
# # #     2. Publishes the final success message with a GDrive download link for the user.
# # #     3. Triggers a silent, chained background task to transfer the file to Telegram for archival.
# # #     """
# # #     file_path = Path(file_path_str)
# # #     progress = ProgressManager(file_id)
# # #     gdrive_id = None

# # #     try:
# # #         print(f"[{file_id}] [GDRIVE_TASK] Starting GDrive upload.")
# # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# # #         # --- Authentication and Session Initialization ---
# # #         from google.oauth2.credentials import Credentials
# # #         from google.auth.transport.requests import AuthorizedSession
# # #         creds = Credentials.from_authorized_user_info(info={"client_id": settings.OAUTH_CLIENT_ID, "client_secret": settings.OAUTH_CLIENT_SECRET, "refresh_token": settings.OAUTH_REFRESH_TOKEN}, scopes=['https://www.googleapis.com/auth/drive'])
# # #         authed_session = AuthorizedSession(creds)
# # #         total_size = os.path.getsize(file_path)
# # #         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# # #         headers = {'Content-Type': 'application/json; charset=UTF-8'}
# # #         init_response = authed_session.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable', headers=headers, data=json.dumps(metadata))
# # #         init_response.raise_for_status()
# # #         upload_url = init_response.headers['Location']

# # #         # --- Chunked Upload with Progress Reporting ---
# # #         bytes_sent = 0
# # #         last_reported_percentage = -1
# # #         with open(file_path, 'rb') as f:
# # #             while True:
# # #                 chunk = f.read(DRIVE_CHUNK_SIZE)
# # #                 if not chunk: break
# # #                 start_byte, end_byte = bytes_sent, bytes_sent + len(chunk) - 1
# # #                 content_range = f"bytes {start_byte}-{end_byte}/{total_size}"
# # #                 upload_response = authed_session.put(upload_url, headers={'Content-Range': content_range}, data=chunk)
# # #                 upload_response.raise_for_status()
# # #                 bytes_sent += len(chunk)
# # #                 percentage = math.floor((bytes_sent / total_size) * 100)
                
# # #                 # Only publish progress if it has changed to avoid spamming Redis and the client
# # #                 if percentage > last_reported_percentage:
# # #                     progress.publish_progress(percentage)
# # #                     last_reported_percentage = percentage
        
# # #         response_data = upload_response.json()
# # #         gdrive_id = response_data.get('id')
# # #         if not gdrive_id:
# # #             raise Exception("Google Drive upload finished, but no GDrive ID was returned.")
        
# # #         print(f"[{file_id}] [GDRIVE_TASK] GDrive upload successful. GDrive ID: {gdrive_id}")

# # #         # --- User-Facing Success Notification ---
# # #         db.files.update_one(
# # #             {"_id": file_id},
# # #             {"$set": {
# # #                 "gdrive_id": gdrive_id,
# # #                 "status": UploadStatus.COMPLETED,
# # #                 "storage_location": StorageLocation.GDRIVE 
# # #             }}
# # #         )
        
# # #         # Announce success to the user with the correct, full download URL
# # #         download_path = f"/api/v1/download/stream/{file_id}"
# # #         progress.publish_success(download_path)
# # #         print(f"[{file_id}] [GDRIVE_TASK] Published success with download link to user.")

# # #         # --- Silent Background Archival to Telegram ---
# # #         print(f"[{file_id}] [GDRIVE_TASK] Dispatching silent background task for Telegram archival.")
# # #         task_chain = chain(
# # #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# # #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# # #         )
# # #         task_chain.delay()

# # #     except Exception as e:
# # #         print(f"!!! [{file_id}] [GDRIVE_TASK] Main task failed: {e}")
# # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # #         progress.publish_error(str(e))
    
# # #     finally:
# # #         # --- Cleanup ---
# # #         if file_path.exists():
# # #             file_path.unlink()
# # #             print(f"[{file_id}] [GDRIVE_TASK] Cleaned up temp file.")




# # import os
# # import json
# # from pathlib import Path
# # import math
# # from celery import chain

# # # --- NEW, IMPORTANT IMPORT ---
# # from googleapiclient.http import MediaFileUpload

# # from app.celery_worker import celery_app
# # from app.core.config import settings
# # from app.db.mongodb import db
# # from app.models.file import UploadStatus, StorageLocation
# # from app.services import google_drive_service
# # from app.progress_manager import ProgressManager
# # from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# # @celery_app.task(name="tasks.upload_to_drive")
# # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# #     """
# #     This task uses Google's efficient MediaFileUpload object to upload the file,
# #     restoring the original speed while still providing real-time progress updates.
# #     """
# #     file_path = Path(file_path_str)
# #     progress = ProgressManager(file_id)
# #     gdrive_id = None

# #     try:
# #         print(f"[{file_id}] [GDRIVE_TASK] Starting EFFICIENT GDrive upload.")
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# #         # Build the Google Drive service object
# #         service = google_drive_service.get_drive_service()

# #         # --- THIS IS THE EFFICIENT METHOD ---
# #         # 1. Create a MediaFileUpload object. This is the high-level, optimized way to upload.
# #         # It needs the file path, its MIME type, and set resumable=True.
# #         file_metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# #         media = MediaFileUpload(
# #             file_path,
# #             mimetype='application/octet-stream', # A generic type is fine
# #             resumable=True
# #         )

# #         # 2. Create the upload request but DON'T execute it all at once.
# #         request = service.files().create(
# #             body=file_metadata,
# #             media_body=media,
# #             fields='id'
# #         )

# #         # 3. Use a loop with request.next_chunk() to upload and get progress.
# #         # This lets the library manage the upload efficiently while we observe.
# #         response = None
# #         while response is None:
# #             status, response = request.next_chunk()
# #             if status:
# #                 # status.progress() returns a float from 0.0 to 1.0
# #                 percentage = math.floor(status.progress() * 100)
# #                 progress.publish_progress(percentage)
        
# #         gdrive_id = response.get('id')
# #         if not gdrive_id:
# #             raise Exception("Google Drive upload finished, but no GDrive ID was returned.")
        
# #         print(f"[{file_id}] [GDRIVE_TASK] GDrive upload successful. GDrive ID: {gdrive_id}")

# #         # --- The rest of the logic remains the same ---
# #         db.files.update_one(
# #             {"_id": file_id},
# #             {"$set": {
# #                 "gdrive_id": gdrive_id,
# #                 "status": UploadStatus.COMPLETED,
# #                 "storage_location": StorageLocation.GDRIVE 
# #             }}
# #         )
        
# #         download_path = f"/api/v1/download/stream/{file_id}"
# #         progress.publish_success(download_path)
# #         print(f"[{file_id}] [GDRIVE_TASK] Published success with download link to user.")

# #         print(f"[{file_id}] [GDRIVE_TASK] Dispatching silent background task for Telegram archival.")
# #         task_chain = chain(
# #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# #         )
# #         task_chain.delay()

# #     except Exception as e:
# #         print(f"!!! [{file_id}] [GDRIVE_TASK] Main task failed: {e}")
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# #         progress.publish_error(str(e))
    
# #     finally:
# #         if file_path.exists():
# #             file_path.unlink()
# #             print(f"[{file_id}] [GDRIVE_TASK] Cleaned up temp file.")


# ##### correct but temp file not remove#####

# # import os
# # from pathlib import Path
# # import math
# # from celery import chain

# # # Important imports from the Google library
# # from googleapiclient.http import MediaFileUpload
# # from google.oauth2.credentials import Credentials
# # from googleapiclient.discovery import build

# # from app.celery_worker import celery_app
# # from app.core.config import settings
# # from app.db.mongodb import db
# # from app.models.file import UploadStatus, StorageLocation
# # from app.progress_manager import ProgressManager
# # from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# # @celery_app.task(name="tasks.upload_to_drive")
# # def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
# #     """
# #     This task uses the EFFICIENT MediaFileUpload method while authenticating
# #     as the USER (not a service account) to solve the storage quota error.
# #     """
# #     file_path = Path(file_path_str)
# #     progress = ProgressManager(file_id)
# #     gdrive_id = None
# #     media = None  # Define here to be accessible in finally block

# #     try:
# #         print(f"[{file_id}] [GDRIVE_TASK] Starting EFFICIENT upload as USER.")
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

# #         # --- FIX #1: Authenticate as the USER using OAuth credentials ---
# #         # This is the crucial step that was missing.
# #         creds = Credentials.from_authorized_user_info(info={
# #             "client_id": settings.OAUTH_CLIENT_ID,
# #             "client_secret": settings.OAUTH_CLIENT_SECRET,
# #             "refresh_token": settings.OAUTH_REFRESH_TOKEN,
# #         }, scopes=['https://www.googleapis.com/auth/drive'])

# #         # Build the Drive service using the user's credentials
# #         service = build('drive', 'v3', credentials=creds)

# #         # --- FIX #2: Use the fast MediaFileUpload object ---
# #         file_metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
# #         media = MediaFileUpload(
# #             file_path_str, # Pass the string path directly
# #             mimetype='application/octet-stream',
# #             resumable=True
# #         )

# #         request = service.files().create(
# #             body=file_metadata,
# #             media_body=media,
# #             fields='id'
# #         )

# #         # Loop to get progress while the library handles the efficient upload
# #         response = None
# #         while response is None:
# #             status, response = request.next_chunk()
# #             if status:
# #                 percentage = math.floor(status.progress() * 100)
# #                 progress.publish_progress(percentage)
        
# #         gdrive_id = response.get('id')
# #         if not gdrive_id:
# #             raise Exception("Google Drive upload finished, but no GDrive ID was returned.")
        
# #         print(f"[{file_id}] [GDRIVE_TASK] GDrive upload successful. GDrive ID: {gdrive_id}")

# #         # --- The rest of the success logic is unchanged ---
# #         db.files.update_one(
# #             {"_id": file_id},
# #             {"$set": {
# #                 "gdrive_id": gdrive_id, "status": UploadStatus.COMPLETED, "storage_location": StorageLocation.GDRIVE 
# #             }}
# #         )
        
# #         download_path = f"/api/v1/download/stream/{file_id}"
# #         progress.publish_success(download_path)
# #         print(f"[{file_id}] [GDRIVE_TASK] Published success to user.")

# #         print(f"[{file_id}] [GDRIVE_TASK] Dispatching silent Telegram archival task.")
# #         task_chain = chain(
# #             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
# #             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
# #         )
# #         task_chain.delay()

# #     except Exception as e:
# #         print(f"!!! [{file_id}] [GDRIVE_TASK] Main task failed: {e}")
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# #         progress.publish_error(str(e))
    
# #     finally:
# #         # --- FIX #3: Robust Cleanup ---
# #         # Ensure media object reference is cleared to help release the file lock
# #         media = None
# #         if file_path.exists():
# #             try:
# #                 file_path.unlink()
# #                 print(f"[{file_id}] [GDRIVE_TASK] Cleaned up temp file.")
# #             except Exception as cleanup_e:
# #                 # Log a cleanup error but don't crash the task
# #                 print(f"!!! [{file_id}] [GDRIVE_TASK] Error during file cleanup: {cleanup_e}")



# import os
# import json
# from pathlib import Path
# import math
# from celery import chain

# # We only need the Credentials and AuthorizedSession for this robust method
# from google.oauth2.credentials import Credentials
# from google.auth.transport.requests import AuthorizedSession

# from app.celery_worker import celery_app
# from app.core.config import settings
# from app.db.mongodb import db
# from app.models.file import UploadStatus, StorageLocation
# from app.progress_manager import ProgressManager
# from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

# DRIVE_CHUNK_SIZE = 4 * 1024 * 1024 # 4MB

# @celery_app.task(name="tasks.upload_to_drive")
# def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
#     """
#     This is the definitive, reliable upload task. It fixes all previous issues by:
#     1. Using User OAuth Credentials to avoid storage quota errors.
#     2. Using a manual resumable session to provide progress.
#     3. Using a 'with open' block to guarantee the temp file is unlocked and can be deleted.
#     """
#     file_path = Path(file_path_str)
#     progress = ProgressManager(file_id)
#     gdrive_id = None

#     try:
#         print(f"[{file_id}] [GDRIVE_TASK] Starting RELIABLE upload as USER.")
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

#         # --- STEP 1: Correctly Authenticate as the User ---
#         creds = Credentials.from_authorized_user_info(info={
#             "client_id": settings.OAUTH_CLIENT_ID,
#             "client_secret": settings.OAUTH_CLIENT_SECRET,
#             "refresh_token": settings.OAUTH_REFRESH_TOKEN,
#         }, scopes=['https://www.googleapis.com/auth/drive'])
#         authed_session = AuthorizedSession(creds)
        
#         # --- STEP 2: Initiate a Resumable Upload Session ---
#         total_size = os.path.getsize(file_path)
#         metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
#         headers = {'Content-Type': 'application/json; charset=UTF-8'}
        
#         init_response = authed_session.post(
#             'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable',
#             headers=headers,
#             data=json.dumps(metadata)
#         )
#         init_response.raise_for_status()
#         upload_url = init_response.headers['Location']

#         # --- STEP 3: Upload the file with reliable file handling ---
#         # The 'with open' block guarantees the file is closed before the 'finally' block runs.
#         with open(file_path, 'rb') as f:
#             # The entire file is sent in one go to the resumable URL.
#             # Google's server handles the progress on its end.
#             # While this looks like one big request, it's a stream to the resumable endpoint.
#             upload_response = authed_session.put(upload_url, data=f)
#             upload_response.raise_for_status()
#             response_data = upload_response.json()

#         # The 'with' block has closed the file, releasing the lock.
#         progress.publish_progress(100)
        
#         gdrive_id = response_data.get('id')
#         if not gdrive_id:
#             raise Exception("Google Drive upload finished, but no GDrive ID was returned.")
        
#         print(f"[{file_id}] [GDRIVE_TASK] GDrive upload successful. GDrive ID: {gdrive_id}")

#         # --- Success logic remains the same ---
#         db.files.update_one(
#             {"_id": file_id},
#             {"$set": {
#                 "gdrive_id": gdrive_id, "status": UploadStatus.COMPLETED, "storage_location": StorageLocation.GDRIVE 
#             }}
#         )
        
#         download_path = f"/api/v1/download/stream/{file_id}"
#         progress.publish_success(download_path)
#         print(f"[{file_id}] [GDRIVE_TASK] Published success to user.")

#         print(f"[{file_id}] [GDRIVE_TASK] Dispatching silent Telegram archival task.")
#         task_chain = chain(
#             transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
#             finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
#         )
#         task_chain.delay()

#     except Exception as e:
#         print(f"!!! [{file_id}] [GDRIVE_TASK] Main task failed: {e}")
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
#         progress.publish_error(str(e))
    
#     finally:
#         # This will now work every time because the 'with open' block has released the file.
#         if file_path.exists():
#             try:
#                 file_path.unlink()
#                 print(f"[{file_id}] [GDRIVE_TASK] Cleaned up temp file successfully.")
#             except Exception as cleanup_e:
#                 print(f"!!! [{file_id}] [GDRIVE_TASK] Error during file cleanup: {cleanup_e}")



#new flow of celery#

import os
import json
from pathlib import Path
import math
from celery import chain

# We only need the Credentials and AuthorizedSession for this robust method
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession

from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus, StorageLocation
from app.progress_manager import ProgressManager
from app.tasks.telegram_uploader_task import transfer_to_telegram, finalize_and_delete

@celery_app.task(name="tasks.upload_to_drive", queue="uploads_queue")
def upload_to_drive_task(file_id: str, file_path_str: str, filename: str):
    # This task is now routed to the 'uploads_queue' automatically.
    file_path = Path(file_path_str)
    progress = ProgressManager(file_id)
    # ... (rest of the code is unchanged and correct)
    try:
        print(f"[{file_id}] [GDRIVE_TASK] Starting RELIABLE upload as USER.")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

        creds = Credentials.from_authorized_user_info(info={
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET,
            "refresh_token": settings.OAUTH_REFRESH_TOKEN,
        }, scopes=['https://www.googleapis.com/auth/drive'])
        authed_session = AuthorizedSession(creds)
        
        total_size = os.path.getsize(file_path)
        metadata = {'name': filename, 'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]}
        headers = {'Content-Type': 'application/json; charset=UTF-8'}
        
        init_response = authed_session.post(
            'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable',
            headers=headers,
            data=json.dumps(metadata)
        )
        init_response.raise_for_status()
        upload_url = init_response.headers['Location']

        with open(file_path, 'rb') as f:
            upload_response = authed_session.put(upload_url, data=f)
            upload_response.raise_for_status()
            response_data = upload_response.json()

        progress.publish_progress(100)
        
        gdrive_id = response_data.get('id')
        if not gdrive_id:
            raise Exception("Google Drive upload finished, but no GDrive ID was returned.")
        
        print(f"[{file_id}] [GDRIVE_TASK] GDrive upload successful. GDrive ID: {gdrive_id}")

        db.files.update_one(
            {"_id": file_id},
            {"$set": {
                "gdrive_id": gdrive_id, "status": UploadStatus.COMPLETED, "storage_location": StorageLocation.GDRIVE 
            }}
        )
        
        download_path = f"/api/v1/download/stream/{file_id}"
        progress.publish_success(download_path)
        print(f"[{file_id}] [GDRIVE_TASK] Published success to user.")

        print(f"[{file_id}] [GDRIVE_TASK] Dispatching silent Telegram archival task.")
        # This chain will be automatically routed to the 'archive_queue'
        task_chain = chain(
            transfer_to_telegram.s(gdrive_id=gdrive_id, file_id=file_id),
            finalize_and_delete.s(file_id=file_id, gdrive_id=gdrive_id)
        )
        task_chain.delay()

    except Exception as e:
        print(f"!!! [{file_id}] [GDRIVE_TASK] Main task failed: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        progress.publish_error(str(e))
    
    finally:
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"[{file_id}] [GDRIVE_TASK] Cleaned up temp file successfully.")
            except Exception as cleanup_e:
                print(f"!!! [{file_id}] [GDRIVE_TASK] Error during file cleanup: {cleanup_e}")