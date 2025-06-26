from app.db.mongodb import db
from app.services import google_drive_service, telegram_service
from app.models.file import StorageLocation
from bson import ObjectId
import io

CHUNK_SIZE_BYTES = 15 * 1024 * 1024  # 15MB

async def transfer_gdrive_to_telegram(file_id: str):
    print(f"Starting transfer task for file_id: {file_id}")
    file_meta_doc = db.files.find_one({"_id": file_id})
    if not file_meta_doc or not file_meta_doc.get("gdrive_id"):
        print(f"File {file_id} not found or has no gdrive_id.")
        return

    gdrive_id = file_meta_doc["gdrive_id"]

    try:
        # 1. Download file from Google Drive into memory
        print(f"Downloading {gdrive_id} from GDrive...")
        file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
        # 2. Split into chunks and upload to Telegram
        message_ids = []
        file_bytes_io.seek(0)
        chunk_num = 0
        while True:
            chunk = file_bytes_io.read(CHUNK_SIZE_BYTES)
            if not chunk:
                break
            chunk_num += 1
            filename = f"{file_id}_part_{chunk_num}"
            print(f"Uploading chunk {chunk_num} to Telegram...")
            message_id = await telegram_service.upload_chunk_to_telegram(chunk, filename)
            message_ids.append(message_id)

        print(f"All chunks uploaded. Message IDs: {message_ids}")

        # 3. Update MongoDB record
        db.files.update_one(
            {"_id": file_id},
            {
                "$set": {
                    "storage_location": StorageLocation.TELEGRAM,
                    "telegram_message_ids": message_ids
                },
                "$unset": {"gdrive_id": ""}
            }
        )
        print(f"Updated MongoDB record for {file_id}.")

        # 4. Delete file from Google Drive
        google_drive_service.delete_file_from_gdrive(gdrive_id)
        
    except Exception as e:
        print(f"An error occurred during transfer for file {file_id}: {e}")
        # Here you would add retry logic or error logging