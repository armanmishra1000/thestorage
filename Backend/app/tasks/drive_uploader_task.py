import os
from pathlib import Path
import json

from celery import Celery
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload # Import the official helper
from app.tasks.telegram_transfer_task import transfer_drive_to_telegram
from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus

from app.progress_manager import ProgressManager

# This is the chunk size the Google library will use. 64MB is a great for speed.
CHUNKSIZE = 64 * 1024 * 1024

@celery_app.task(name="tasks.oauth_resumable_upload")
def oauth_resumable_upload(file_id: str, file_path_str: str, filename: str):
    """
    The definitive upload task. Uses OAuth 2.0 for authentication and the official
    Google library's resumable uploader for maximum reliability and good speed.
    """
    file_path = Path(file_path_str)
    gdrive_id = None
    # --- NEW: Instantiate the ProgressManager ---
    progress_manager = ProgressManager(file_id)
    
    try:
        print(f"[CELERY_WORKER] Starting RELIABLE SEQUENTIAL upload for {file_id}")
        
        # 1. AUTHENTICATION (This part is proven to work)
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
        
        service = build("drive", "v3", credentials=creds)
        
        # 2. FILE METADATA
        file_metadata = {
            "name": filename,
            "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]
        }
        
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

        # 3. RELIABLE SEQUENTIAL UPLOAD
        # We use a 'with open' block to guarantee the file handle is closed, preventing PermissionErrors.
        with open(file_path, "rb") as file_handle:
            # Create the special MediaIoBaseUpload object
            media = MediaIoBaseUpload(
                file_handle, 
                mimetype='application/octet-stream', 
                chunksize=CHUNKSIZE, 
                resumable=True
            )
            
            # Create the request object
            request = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            )
            
            # Execute the upload in a loop that handles the chunks for us
            response = None
            while response is None:
                # next_chunk() sends the next part of the file
                status, response = request.next_chunk()
                if status:
                    progress_percentage = int(status.progress() * 100)
                    progress_manager.publish_progress(progress_percentage)
                    # print(f"[GOOGLE_UPLOADER] Uploaded {int(status.progress() * 100)}%")
        
        gdrive_id = response.get('id')
        download_link = response.get('webViewLink')
        if not gdrive_id:
            raise Exception("Upload seemed to succeed, but no file ID was returned.")

        print(f"[CELERY_WORKER] Upload successful! GDrive ID: {gdrive_id}")

        # 4. FINALIZE DATABASE
        db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": "gdrive_completed", "storage_location": "gdrive", "gdrive_id": gdrive_id}} # We'll use a more specific status
            )
        print(f"[CELERY_WORKER] Successfully finalized GDrive upload for {file_id}.")
        
        progress_manager.publish_success(download_link)

        
        # --- THIS IS THE NEW LINE ---
            # Now, trigger the next task in the chain
        print(f"[CELERY_WORKER] Queuing task to transfer {file_id} to Telegram.")
        transfer_drive_to_telegram.delay(file_id=file_id, gdrive_id=gdrive_id)
            # --- END OF NEW LINE ---
        
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        print(f"!!! [CELERY_WORKER] Upload FAILED for {file_id}: {error_msg}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        
        progress_manager.publish_error(error_msg)
        
    finally:
        # 5. CLEANUP
        # This will now work because the 'with open' block closed the file.
        if file_path.exists():
            file_path.unlink()
            print(f"[CELERY_WORKER] Cleaned up temp file.")