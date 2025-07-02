import asyncio
import io
from app.celery_worker import celery_app
from app.services import google_drive_service, telegram_service
from app.db.mongodb import db # Import the db object

@celery_app.task(name="tasks.transfer_to_telegram")
def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[int]:
    """
    Celery task to download a file from Google Drive, split it into chunks,
    and upload each chunk to Telegram.
    
    Args:
        gdrive_id: The ID of the file in Google Drive.
        file_id: The internal ID of our file, used to fetch metadata.

    Returns:
        A list of message_ids for the uploaded chunks in Telegram.
    """
    print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
    
    try:
        # First, get the original filename from our database
        file_doc = db.files.find_one({"_id": file_id})
        if not file_doc:
            raise Exception(f"Could not find file metadata for internal id {file_id}")
        original_filename = file_doc.get("filename", "untitled.dat")

        # 1. Download the full file from Google Drive into memory
        file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
        # 2. Split into chunks and upload to Telegram
        message_ids = []
        chunk_num = 1
        
        while True:
            chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
            if not chunk_data:
                break # End of file
            
            chunk_filename = f"{original_filename}.part_{chunk_num}"
            
            message_id = asyncio.run(
                telegram_service.upload_file_chunk(chunk_data, chunk_filename)
            )
            message_ids.append(message_id)
            chunk_num += 1
            
        print(f"[TELEGRAM_TASK] All chunks transferred for GDrive file: {gdrive_id}")
        return message_ids

    except Exception as e:
        print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
        raise