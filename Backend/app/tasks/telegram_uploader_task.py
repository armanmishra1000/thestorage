# # # # import asyncio
# # # # import io
# # # # from app.celery_worker import celery_app
# # # # from app.services import google_drive_service, telegram_service
# # # # from app.db.mongodb import db # Import the db object
# # # # import time

# # # # @celery_app.task(name="tasks.transfer_to_telegram")
# # # # def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[int]:
# # # #     """
# # # #     Celery task to download a file from Google Drive, split it into chunks,
# # # #     and upload each chunk to Telegram.
    
# # # #     Args:
# # # #         gdrive_id: The ID of the file in Google Drive.
# # # #         file_id: The internal ID of our file, used to fetch metadata.

# # # #     Returns:
# # # #         A list of message_ids for the uploaded chunks in Telegram.
# # # #     """
# # # #     print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
    
# # # #     try:
# # # #         # First, get the original filename from our database
# # # #         file_doc = db.files.find_one({"_id": file_id})
# # # #         if not file_doc:
# # # #             raise Exception(f"Could not find file metadata for internal id {file_id}")
# # # #         original_filename = file_doc.get("filename", "untitled.dat")

# # # #         # 1. Download the full file from Google Drive into memory
# # # #         file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
# # # #         # 2. Split into chunks and upload to Telegram
# # # #         message_ids = []
# # # #         chunk_num = 1
        
# # # #         while True:
# # # #             chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
# # # #             if not chunk_data:
# # # #                 break # End of file
            
# # # #             chunk_filename = f"{original_filename}.part_{chunk_num}"
            
# # # #             message_id = asyncio.run(
# # # #                 telegram_service.upload_file_chunk(chunk_data, chunk_filename)
# # # #             )
# # # #             message_ids.append(message_id)
# # # #             chunk_num += 1
            
# # # #             print("[TELEGRAM_TASK] Waiting for 3 seconds to avoid rate limit...")
# # # #             time.sleep(3) 
            
# # # #         print(f"[TELEGRAM_TASK] All chunks transferred for GDrive file: {gdrive_id}")
# # # #         return message_ids

# # # #     except Exception as e:
# # # #         print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
# # # #         raise


# # # # Backend/app/tasks/telegram_uploader_task.py

# # # import asyncio
# # # import io
# # # import time
# # # from app.celery_worker import celery_app
# # # from app.services import google_drive_service, telegram_service
# # # from app.db.mongodb import db
# # # from app.models.file import UploadStatus, StorageLocation
# # # from app.progress_manager import ProgressManager

# # # @celery_app.task(name="tasks.transfer_to_telegram")
# # # def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[int]:
# # #     """
# # #     Celery task to download a file from GDrive, split it, and upload to Telegram.
# # #     This task now returns the list of message_ids to the next task in the chain.
# # #     """
# # #     print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
    
# # #     try:
# # #         file_doc = db.files.find_one({"_id": file_id})
# # #         if not file_doc:
# # #             raise Exception(f"Could not find file metadata for internal id {file_id}")
# # #         original_filename = file_doc.get("filename", "untitled.dat")

# # #         file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
# # #         message_ids = []
# # #         chunk_num = 1
        
# # #         while True:
# # #             chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
# # #             if not chunk_data:
# # #                 break
            
# # #             chunk_filename = f"{original_filename}.part_{chunk_num}"
            
# # #             message_id = asyncio.run(
# # #                 telegram_service.upload_file_chunk(chunk_data, chunk_filename)
# # #             )
# # #             message_ids.append(message_id)
# # #             chunk_num += 1
            
# # #             print("[TELEGRAM_TASK] Waiting for 3 seconds to avoid rate limit...")
# # #             time.sleep(3) 
            
# # #         print(f"[TELEGRAM_TASK] All chunks transferred for GDrive file: {gdrive_id}")
# # #         # The return value of this task is automatically passed to the next task in the chain.
# # #         return message_ids

# # #     except Exception as e:
# # #         print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
# # #         # Notify user of failure
# # #         progress = ProgressManager(file_id)
# # #         progress.publish_error(str(e))
# # #         raise

# # # # --- THIS TASK IS NOW IN THE CORRECT FILE ---
# # # @celery_app.task(name="tasks.finalize_and_delete")
# # # def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
# # #     """
# # #     This is the final task. It updates the DB, notifies the user, and cleans up.
# # #     """
# # #     progress = ProgressManager(file_id)
# # #     try:
# # #         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
# # #         db.files.update_one(
# # #             {"_id": file_id},
# # #             {
# # #                 "$set": {
# # #                     "status": UploadStatus.COMPLETED,
# # #                     "storage_location": StorageLocation.TELEGRAM,
# # #                     "telegram_message_ids": telegram_message_ids
# # #                 },
# # #                 "$unset": {"gdrive_id": ""}
# # #             }
# # #         )
# # #         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

# # #         # Announce success to the user
# # #         download_path = f"/download/{file_id}"
# # #         progress.publish_success(download_path)
# # #         print(f"[FINALIZER_TASK] Published success message for {file_id}.")

# # #         # Clean up the file from Google Drive
# # #         google_drive_service.delete_file_with_refresh_token(gdrive_id)

# # #     except Exception as e:
# # #         progress.publish_error(f"Failed during finalization: {e}")
# # #         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")

# # # Backend/app/tasks/telegram_uploader_task.py

# # import asyncio
# # import io
# # import time
# # from app.celery_worker import celery_app
# # from app.services import google_drive_service, telegram_service
# # from app.db.mongodb import db
# # from app.models.file import UploadStatus, StorageLocation
# # from app.progress_manager import ProgressManager

# # # --- NEW HELPER FUNCTION ---
# # def run_async(coro):
# #     """
# #     A helper function to safely run an async coroutine from a sync context.
# #     It gets the existing event loop if one is running (like with gevent),
# #     or creates a new one if not.
# #     """
# #     try:
# #         loop = asyncio.get_running_loop()
# #     except RuntimeError:  # 'RuntimeError: There is no current event loop...'
# #         loop = asyncio.new_event_loop()
# #         asyncio.set_event_loop(loop)
# #     return loop.run_until_complete(coro)

# # @celery_app.task(name="tasks.transfer_to_telegram")
# # def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[int]:
# #     """
# #     Celery task to download from GDrive, split, and upload to Telegram.
# #     """
# #     print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
    
# #     try:
# #         file_doc = db.files.find_one({"_id": file_id})
# #         if not file_doc:
# #             raise Exception(f"Could not find file metadata for internal id {file_id}")
# #         original_filename = file_doc.get("filename", "untitled.dat")

# #         file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
# #         message_ids = []
# #         chunk_num = 1
        
# #         while True:
# #             chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
# #             if not chunk_data:
# #                 break
            
# #             chunk_filename = f"{original_filename}.part_{chunk_num}"
            
# #             # --- THIS IS THE KEY FIX ---
# #             # Use our robust helper instead of the simple asyncio.run()
# #             message_id = run_async(
# #                 telegram_service.upload_file_chunk(chunk_data, chunk_filename)
# #             )
# #             message_ids.append(message_id)
# #             chunk_num += 1
            
# #             print("[TELEGRAM_TASK] Waiting for 3 seconds to avoid rate limit...")
# #             time.sleep(3) 
            
# #         print(f"[TELEGRAM_TASK] All chunks transferred for GDrive file: {gdrive_id}")
# #         return message_ids

# #     except Exception as e:
# #         print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
# #         progress = ProgressManager(file_id)
# #         progress.publish_error(str(e))
# #         raise

# # # (The finalize_and_delete task remains unchanged and is correct)
# # @celery_app.task(name="tasks.finalize_and_delete")
# # def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
# #     # ... (no changes needed here)
# #     progress = ProgressManager(file_id)
# #     try:
# #         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
# #         db.files.update_one(
# #             {"_id": file_id},
# #             {
# #                 "$set": {
# #                     "status": UploadStatus.COMPLETED,
# #                     "storage_location": StorageLocation.TELEGRAM,
# #                     "telegram_message_ids": telegram_message_ids
# #                 },
# #                 "$unset": {"gdrive_id": ""}
# #             }
# #         )
# #         print(f"[FINALIZER_TASK] Database updated for {file_id}.")

# #         download_path = f"/download/{file_id}"
# #         progress.publish_success(download_path)
# #         print(f"[FINALIZER_TASK] Published success message for {file_id}.")

# #         google_drive_service.delete_file_with_refresh_token(gdrive_id)

# #     except Exception as e:
# #         progress.publish_error(f"Failed during finalization: {e}")
# #         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")


# # Backend/app/tasks/telegram_uploader_task.py

# # NO LONGER NEED ASYNCIO
# import io
# import time
# from app.celery_worker import celery_app
# from app.services import google_drive_service, telegram_service
# from app.db.mongodb import db
# from app.models.file import UploadStatus, StorageLocation
# from app.progress_manager import ProgressManager

# @celery_app.task(name="tasks.transfer_to_telegram")
# def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[int]:
#     """
#     This task is now fully synchronous.
#     """
#     print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
#     try:
#         file_doc = db.files.find_one({"_id": file_id})
#         if not file_doc:
#             raise Exception(f"Could not find file metadata for internal id {file_id}")
#         original_filename = file_doc.get("filename", "untitled.dat")

#         file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
#         message_ids = []
#         chunk_num = 1
        
#         while True:
#             chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
#             if not chunk_data:
#                 break
            
#             chunk_filename = f"{original_filename}.part_{chunk_num}"
            
#             # --- THE KEY FIX: Direct synchronous call ---
#             message_id = telegram_service.upload_file_chunk(chunk_data, chunk_filename)
#             message_ids.append(message_id)
#             chunk_num += 1
            
#             print("[TELEGRAM_TASK] Waiting for 3 seconds to avoid rate limit...")
#             time.sleep(3) 
            
#         print(f"[TELEGRAM_TASK] All chunks transferred for GDrive file: {gdrive_id}")
#         return message_ids

#     except Exception as e:
#         print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
#         progress = ProgressManager(file_id)
#         progress.publish_error(str(e))
#         raise

# @celery_app.task(name="tasks.finalize_and_delete")
# def finalize_and_delete(telegram_message_ids: list[int], file_id: str, gdrive_id: str):
#     """
#     This task is now silent. It cleans up without notifying the user,
#     as they have already been notified.
#     """
#     try:
#         print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
#         db.files.update_one(
#             {"_id": file_id},
#             {
#                 "$set": {
#                     "storage_location": StorageLocation.TELEGRAM,
#                     "telegram_message_ids": telegram_message_ids
#                 },
#                 "$unset": {"gdrive_id": ""}
#             }
#         )
#         print(f"[FINALIZER_TASK] Database updated for {file_id}.")
#         google_drive_service.delete_file_with_refresh_token(gdrive_id)
#     except Exception as e:
#         # If this fails, we don't notify the user again. We just log it.
#         print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")


# Backend/app/tasks/telegram_uploader_task.py

import io
import time
from app.celery_worker import celery_app
from app.services import google_drive_service, telegram_service
from app.db.mongodb import db
from app.models.file import UploadStatus, StorageLocation
from app.progress_manager import ProgressManager

@celery_app.task(name="tasks.transfer_to_telegram")
def transfer_to_telegram(gdrive_id: str, file_id: str) -> list[str]: # Return type is now list[str]
    """
    Downloads from GDrive and uploads to Telegram, returning a list of file_ids.
    """
    print(f"[TELEGRAM_TASK] Starting transfer for GDrive file: {gdrive_id}")
    try:
        file_doc = db.files.find_one({"_id": file_id})
        original_filename = file_doc.get("filename", "untitled.dat")
        file_bytes_io = google_drive_service.download_file_from_gdrive(gdrive_id)
        
        file_ids = [] # Changed from message_ids
        chunk_num = 1
        
        while True:
            chunk_data = file_bytes_io.read(telegram_service.TELEGRAM_CHUNK_SIZE_BYTES)
            if not chunk_data:
                break
            
            chunk_filename = f"{original_filename}.part_{chunk_num}"
            
            # Use the new service function that returns a file_id (string)
            new_file_id = telegram_service.upload_chunk_and_get_file_id(chunk_data, chunk_filename)
            file_ids.append(new_file_id)
            chunk_num += 1
            
            print("[TELEGRAM_TASK] Waiting for 3 seconds to avoid rate limit...")
            time.sleep(3) 
            
        print(f"[TELEGRAM_TASK] All chunks transferred. File IDs: {file_ids}")
        return file_ids

    except Exception as e:
        print(f"!!! [TELEGRAM_TASK] Failed to transfer {gdrive_id} to Telegram: {e}")
        progress = ProgressManager(file_id)
        progress.publish_error(str(e))
        raise

@celery_app.task(name="tasks.finalize_and_delete")
def finalize_and_delete(file_ids: list[str], file_id: str, gdrive_id: str): # Now receives list[str]
    """
    This is the final task. It saves the correct field name.
    """
    progress = ProgressManager(file_id)
    try:
        print(f"[FINALIZER_TASK] Finalizing task for file_id: {file_id}")
        db.files.update_one(
            {"_id": file_id},
            {
                "$set": {
                    "status": UploadStatus.COMPLETED,
                    "storage_location": StorageLocation.TELEGRAM,
                    "telegram_file_ids": file_ids # <-- Use the correct field name
                },
                "$unset": {"gdrive_id": ""}
            }
        )
        print(f"[FINALIZER_TASK] Database updated for {file_id}.")

        download_path = f"/download/{file_id}"
        progress.publish_success(download_path)
        print(f"[FINALIZER_TASK] Published success message for {file_id}.")

        google_drive_service.delete_file_with_refresh_token(gdrive_id)

    except Exception as e:
        progress.publish_error(f"Failed during finalization: {e}")
        print(f"!!! [FINALIZER_TASK] Failed during finalization for {file_id}: {e}")