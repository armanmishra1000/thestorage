# import asyncio
# import os
# import random
# from pathlib import Path
# import json

# import httpx
# from celery import Celery
# from google.auth.transport.requests import Request
# from google.oauth2.credentials import Credentials
# from googleapiclient.discovery import build

# from app.celery_worker import celery_app
# from app.core.config import settings
# from app.db.mongodb import db
# from app.models.file import UploadStatus

# # --- PERFORMANCE TUNING CONSTANTS ---
# # Increase the chunk size for faster transfers on good connections.
# # 64MB is a good starting point. Must be a multiple of 256KB.
# CHUNK_SIZE = 64 * 1024 * 1024
# # The number of chunks to upload in parallel. Keep this low (4-8) to avoid rate limits.
# CONCURRENCY_LIMIT = 4
# # Max number of retries for a single chunk.
# MAX_CHUNK_RETRIES = 5

# async def upload_chunk_parallel(
#     client: httpx.AsyncClient,
#     upload_url: str,
#     file_path: Path,
#     chunk_info: dict,
#     access_token: str,
#     semaphore: asyncio.Semaphore,
# ):
#     """
#     Uploads a single chunk in parallel, controlled by a semaphore, with retries.
#     """
#     async with semaphore: # This will wait until a "slot" is available
#         start, size, total_size = chunk_info["start"], chunk_info["size"], chunk_info["total_size"]
#         end = start + size - 1
#         headers = {
#             "Content-Length": str(size),
#             "Content-Range": f"bytes {start}-{end}/{total_size}",
#             "Authorization": f"Bearer {access_token}",
#         }

#         with open(file_path, "rb") as f:
#             f.seek(start)
#             chunk_data = f.read(size)

#         for attempt in range(MAX_CHUNK_RETRIES):
#             try:
#                 print(f"[PARALLEL_UPLOADER] Attempt {attempt + 1} for chunk bytes {start}-{end}")
#                 res = await client.put(upload_url, content=chunk_data, headers=headers, timeout=300.0) # Increased timeout for large chunks
                
#                 if res.status_code in [200, 201, 308]:
#                     print(f"[PARALLEL_UPLOADER] Chunk {start}-{end} succeeded.")
#                     return True

#                 res.raise_for_status()

#             except httpx.HTTPStatusError as e:
#                 if e.response.status_code >= 500 and attempt < MAX_CHUNK_RETRIES - 1:
#                     wait_time = (2**attempt) + random.uniform(0, 1)
#                     print(f"!! Server error on chunk {start}-{end}. Retrying in {wait_time:.2f}s...")
#                     await asyncio.sleep(wait_time)
#                 else:
#                     print(f"!! Unrecoverable error on chunk {start}-{end}: {e}")
#                     return False # Signal failure for this chunk
    
#     return False # All retries failed

# @celery_app.task(name="tasks.oauth_resumable_upload")
# def oauth_resumable_upload(file_id: str, file_path_str: str, filename: str):
#     file_path = Path(file_path_str)

#     async def _run_parallel_upload():
#         gdrive_id = None
#         try:
#             print(f"[CELERY_WORKER] Starting HIGH-SPEED PARALLEL upload for {file_id}")
#             # --- Authentication and Session Initiation (this part is correct and stays the same) ---
#             with open(settings.GOOGLE_OAUTH_CREDENTIALS_PATH, 'r') as f:
#                 client_config = json.load(f)['installed']
#             creds = Credentials(token=None, refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN, token_uri=client_config['token_uri'], client_id=client_config['client_id'], client_secret=client_config['client_secret'], scopes=['https://www.googleapis.com/auth/drive'])
#             creds.refresh(Request())
#             access_token = creds.token
            
#             total_size = os.path.getsize(file_path)
#             metadata = {"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
#             headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}
            
#             async with httpx.AsyncClient() as client:
#                 r = await client.post("https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable", headers=headers, json=metadata)
#                 r.raise_for_status()
#                 upload_url = r.headers["Location"]
            
#             db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_DRIVE}})

#             # --- The Parallel Upload Logic ---
#             chunks_to_process = [
#                 {"start": i, "size": min(CHUNK_SIZE, total_size - i), "total_size": total_size}
#                 for i in range(0, total_size, CHUNK_SIZE)
#             ]
            
#             semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
            
#             async with httpx.AsyncClient() as client:
#                 print(f"Starting parallel upload with concurrency limit of {CONCURRENCY_LIMIT} and chunk size of {CHUNK_SIZE / 1024 / 1024}MB...")
#                 tasks = [
#                     upload_chunk_parallel(client, upload_url, file_path, chunk, access_token, semaphore)
#                     for chunk in chunks_to_process
#                 ]
                
#                 results = await asyncio.gather(*tasks)

#             if not all(results):
#                 raise Exception("One or more chunks failed to upload after multiple retries.")
            
#             # Since we can't easily get the gdrive_id from the resumable upload response,
#             # we need to do one final API call to find the file we just created.
#             print("[CELERY_WORKER] Upload complete. Verifying file and getting final ID...")
#             service = build("drive", "v3", credentials=creds)
#             # This is a bit of a hack: find the most recently modified file with the correct name in the folder.
#             # A more robust solution might involve storing the placeholder ID from the resumable session start.
#             response = service.files().list(
#                 q=f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents and name='{filename}'",
#                 orderBy='modifiedTime desc',
#                 pageSize=1,
#                 fields="files(id, name)"
#             ).execute()
            
#             files = response.get('files', [])
#             if not files:
#                 raise Exception("Could not find the uploaded file in Google Drive to confirm.")
            
#             gdrive_id = files[0].get('id')
#             print(f"[CELERY_WORKER] Verified. Final GDrive ID: {gdrive_id}")

#             # --- Finalization (stays the same) ---
#             db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.COMPLETED, "storage_location": "gdrive", "gdrive_id": gdrive_id}})
#             print(f"[CELERY_WORKER] Successfully finalized {file_id} in database.")

#         except Exception as e:
#             print(f"!!! [CELERY_WORKER] PARALLEL UPLOAD FAILED for {file_id}: {e}")
#             db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
#         finally:
#             if file_path.exists():
#                 file_path.unlink()
#             print(f"[CELERY_WORKER] Cleaned up temp file.")

#     asyncio.run(_run_parallel_upload())


import asyncio
import os
import random
from pathlib import Path
import json

import httpx
from celery import Celery
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.celery_worker import celery_app
from app.core.config import settings
from app.db.mongodb import db
from app.models.file import UploadStatus

# --- Configuration Constants ---
# Use a standard chunk size. 16MB is a good, safe value.
CHUNK_SIZE = 16 * 1024 * 1024
# Max number of retries for a single chunk before failing the whole upload.
MAX_CHUNK_RETRIES = 5

async def upload_chunk_sequentially(
    client: httpx.AsyncClient,
    upload_url: str,
    file_path: Path,
    chunk_info: dict,
    access_token: str
):
    """
    Uploads a single chunk with robust retry logic.
    This function will raise an exception if it fails after all retries.
    """
    start, size, total_size = chunk_info["start"], chunk_info["size"], chunk_info["total_size"]
    end = start + size - 1
    headers = {
        "Content-Length": str(size),
        "Content-Range": f"bytes {start}-{end}/{total_size}",
        "Authorization": f"Bearer {access_token}",
    }

    with open(file_path, "rb") as f:
        f.seek(start)
        chunk_data = f.read(size)

    for attempt in range(MAX_CHUNK_RETRIES):
        try:
            print(f"[SEQUENTIAL_UPLOADER] Attempt {attempt + 1}/{MAX_CHUNK_RETRIES} for chunk bytes {start}-{end}")
            res = await client.put(upload_url, content=chunk_data, headers=headers, timeout=120.0)

            # A 200 or 201 means the upload is complete. A 308 means the chunk was accepted.
            if res.status_code in [200, 201, 308]:
                print(f"[SEQUENTIAL_UPLOADER] Chunk {start}-{end} succeeded with status {res.status_code}.")
                return # Success! Exit the function.

            # Raise an exception for any other non-successful status codes.
            res.raise_for_status()

        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500 and attempt < MAX_CHUNK_RETRIES - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"!! [SEQUENTIAL_UPLOADER] Server error {e.response.status_code}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"!! [SEQUENTIAL_UPLOADER] Unrecoverable error for chunk {start}-{end}: {e}")
                raise e  # Re-raise the exception to fail the whole task.

    # If the loop finishes, it means all retries failed.
    raise Exception(f"All retries failed for chunk {start}-{end}.")


@celery_app.task(name="tasks.oauth_resumable_upload")
def oauth_resumable_upload(file_id: str, file_path_str: str, filename: str):
    file_path = Path(file_path_str)

    async def _run_sequential_upload():
        gdrive_id = None
        creds = None
        try:
            # --- THIS IS THE CORRECTED AUTHENTICATION LOGIC ---
            print(f"[CELERY_WORKER] Starting RELIABLE SEQUENTIAL upload for {file_id}")
            
            # 1. Load the client secrets from the oauth-credentials.json file
            with open(settings.GOOGLE_OAUTH_CREDENTIALS_PATH, 'r') as f:
                client_config = json.load(f)['installed']

            # 2. Create a Credentials object using your stored REFRESH TOKEN
            creds = Credentials(
                token=None,  # No initial access token needed, it will be refreshed
                refresh_token=settings.GOOGLE_OAUTH_REFRESH_TOKEN,
                token_uri=client_config['token_uri'],
                client_id=client_config['client_id'],
                client_secret=client_config['client_secret'],
                scopes=['https://www.googleapis.com/auth/drive']
            )
            # --- END OF CORRECTED AUTHENTICATION LOGIC ---

            total_size = os.path.getsize(file_path)
            metadata = {"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
            
            # Use the official Google library to correctly initiate the session
            service = build("drive", "v3", credentials=creds)
            from googleapiclient.http import MediaIoBaseUpload
            CHUNKSIZE = 64 * 1024 * 1024
            
            # The resumable upload logic from here down is correct
            with open(file_path, 'rb') as file_handle:
                media = MediaIoBaseUpload(
                    file_handle, 
                    mimetype='application/octet-stream', 
                    chunksize=CHUNK_SIZE, 
                    resumable=True
                )
                
                request = service.files().create(
                    body=metadata, 
                    media_body=media, 
                    fields='id'
                )
                
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        print(f"[UPLOADER] Uploaded {int(status.progress() * 100)}%")
            
            gdrive_id = response.get('id')
            if not gdrive_id:
                raise Exception("Upload seemed to succeed, but no file ID was returned.")

            print("[CELERY_WORKER] All chunks uploaded successfully!")
            
            db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": UploadStatus.COMPLETED, "storage_location": "gdrive", "gdrive_id": gdrive_id}}
            )
            print(f"[CELERY_WORKER] Successfully finalized {file_id} in database.")

        except Exception as e:
            print(f"!!! [CELERY_WORKER] Main task failed for {file_id}: {e}")
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
            
        finally:
            if file_path.exists():
                file_path.unlink()
                print(f"[CELERY_WORKER] Cleaned up temp file.")


    asyncio.run(_run_sequential_upload())