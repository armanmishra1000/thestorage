import asyncio
import httpx
import os
from pathlib import Path
from app.db.mongodb import db
from app.models.file import UploadStatus
from app.services import google_drive_service
from fastapi.concurrency import run_in_threadpool

# Define a chunk size for the parallel upload. 
# This is the size of the chunks your SERVER will upload to Google.
# A larger size like 16-32MB is good for server-to-server.
PARALLEL_CHUNK_SIZE_BYTES = 16 * 1024 * 1024 

async def upload_chunk(client: httpx.AsyncClient, upload_url: str, file_path: Path, start: int, size: int, total_size: int):
    """
    Asynchronously uploads a single chunk of a file to Google Drive's resumable upload URL.
    """
    end = start + size - 1
    headers = {
        'Content-Length': str(size),
        'Content-Range': f'bytes {start}-{end}/{total_size}'
    }
    print(f"Uploading chunk: {headers['Content-Range']}")
    with open(file_path, "rb") as f:
        f.seek(start)
        chunk_data = f.read(size)
        try:
            res = await client.put(upload_url, content=chunk_data, headers=headers, timeout=120)
            res.raise_for_status() # Will raise an exception for 4xx/5xx responses
            print(f"Chunk {start}-{end} uploaded successfully. Status: {res.status_code}")
            return res
        except httpx.RequestError as e:
            print(f"An error occurred while uploading chunk {start}-{end}: {e}")
            raise

async def parallel_upload_to_drive(file_id: str, file_path: Path, filename: str):
    """
    Orchestrates the high-performance parallel upload from the server disk to Google Drive.
    """
    try:
        total_size = os.path.getsize(file_path)
        print(f"[UPLOADER_TASK] Starting parallel upload for {file_id}. Total size: {total_size} bytes.")

        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

        # --- THIS IS THE FIX ---
        # Run the synchronous Google client library code in a separate thread pool
        # to prevent it from blocking/crashing the main asyncio event loop.
        print("[UPLOADER_TASK] Acquiring Google Drive session in thread pool...")
        gdrive_id, upload_url = await run_in_threadpool(
            google_drive_service.create_resumable_upload_session, 
            filename=filename
        )
        # --- END OF FIX ---

        tasks = []
        async with httpx.AsyncClient() as client:
            for start in range(0, total_size, PARALLEL_CHUNK_SIZE_BYTES):
                chunk_size = min(PARALLEL_CHUNK_SIZE_BYTES, total_size - start)
                task = asyncio.create_task(
                    upload_chunk(client, upload_url, file_path, start, chunk_size, total_size)
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)

        final_response = results[-1]
        if final_response.status_code not in [200, 201]:
             raise Exception(f"Final chunk upload failed with status {final_response.status_code}.")

        print(f"[UPLOADER_TASK] All chunks for {file_id} uploaded successfully.")
        
        db.files.update_one(
            {"_id": file_id},
            {
                "$set": {
                    "status": UploadStatus.COMPLETED,
                    "storage_location": "gdrive", # Update storage location
                    "gdrive_id": gdrive_id
                }
            }
        )
        print(f"[UPLOADER_TASK] Successfully finalized {file_id} in database.")

    except Exception as e:
        print(f"!!! [UPLOADER_TASK] Parallel upload to Drive failed for {file_id}: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
    finally:
        if file_path.exists():
            file_path.unlink()
            print(f"[UPLOADER_TASK] Cleaned up temporary file: {file_path}")