import asyncio
from app.celery_worker import celery_app
from app.db.mongodb import db
from app.models.file import UploadStatus, StorageLocation
from app.services import google_drive_service, telegram_service
from fastapi.concurrency import run_in_threadpool

# Define the chunk size for splitting files for Telegram
TELEGRAM_CHUNK_SIZE = 15 * 1024 * 1024 # 15MB

@celery_app.task(name="tasks.transfer_drive_to_telegram")
def transfer_drive_to_telegram(file_id: str, gdrive_id: str):
    async def _run_transfer():
        try:
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.TRANSFERRING_TO_TELEGRAM}})
            
            # This list will now store Telegram's file_id for each chunk
            telegram_file_ids = []
            chunk_num = 1
            buffer = b''

            async for drive_chunk in google_drive_service.stream_gdrive_file(gdrive_id):
                buffer += drive_chunk
                while len(buffer) >= TELEGRAM_CHUNK_SIZE:
                    telegram_chunk = buffer[:TELEGRAM_CHUNK_SIZE]
                    buffer = buffer[TELEGRAM_CHUNK_SIZE:]
                    
                    chunk_filename = f"{file_id}_part_{chunk_num}.bin"
                    # The upload service now returns the full document object
                    doc_object = await telegram_service.upload_chunk_to_telegram(telegram_chunk, chunk_filename)
                    telegram_file_ids.append(doc_object['file_id'])
                    chunk_num += 1
            
            if buffer:
                chunk_filename = f"{file_id}_part_{chunk_num}.bin"
                doc_object = await telegram_service.upload_chunk_to_telegram(buffer, chunk_filename)
                telegram_file_ids.append(doc_object['file_id'])

            # THE FIELD NAME IS NOW telegram_file_ids
            db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": UploadStatus.COMPLETED, "storage_location": StorageLocation.TELEGRAM, "telegram_file_ids": telegram_file_ids}, "$unset": {"gdrive_id": ""}}
            )
            print(f"[TELEGRAM_TRANSFER_TASK] Database updated for {file_id}")
            
            # --- THIS IS THE FIX ---
            # Run the synchronous delete function in a thread pool
            print(f"[TELEGRAM_TRANSFER_TASK] Deleting file {gdrive_id} from Google Drive...")
            await run_in_threadpool(google_drive_service.delete_file_from_gdrive, file_id=gdrive_id)
            print(f"[TELEGRAM_TRANSFER_TASK] Google Drive cleanup successful for {gdrive_id}.")
            # --- END OF FIX ---

        except Exception as e:
            print(f"!!! [TELEGRAM_TRANSFER_TASK] Failed for {file_id}: {e}")
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
            # In a real app, you might add retry logic here or leave the file in GDrive as a backup

    # Run the async transfer logic from within the synchronous Celery task
    asyncio.run(_run_transfer())