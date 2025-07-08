# from google.oauth2 import service_account
# from googleapiclient.discovery import build
# from googleapiclient.errors import HttpError
# from app.core.config import settings
# import io

# SCOPES = ['https://www.googleapis.com/auth/drive']

# def get_drive_service():
#     """Initializes and returns the Google Drive service client."""
#     creds = service_account.Credentials.from_service_account_file(
#         settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
#     service = build('drive', 'v3', credentials=creds)
#     return service

# def create_resumable_upload_session(filename: str, creds: service_account.Credentials) -> (str, str):
#     """
#     Creates a 0-byte placeholder file on Google Drive to get a stable file ID,
#     then initiates a resumable upload session to update that file.
#     Returns a tuple of (gdrive_id, upload_url).
#     """
#     try:
#         # Create the credentials object from the service account file
#         creds = service_account.Credentials.from_service_account_file(
#             settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
            
#         # Build the high-level service object for simple operations
#         service = build('drive', 'v3', credentials=creds)
        
#         # Step 1: Create a 0-byte placeholder file. This gives us a permanent file ID.
#         file_metadata = {
#             'name': filename,
#             'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
#         }
#         print("[GDRIVE_SERVICE] Creating placeholder file...")
#         placeholder_file = service.files().create(body=file_metadata, fields='id').execute()
#         gdrive_id = placeholder_file.get('id')
#         if not gdrive_id:
#             raise Exception("Failed to create placeholder file in Google Drive.")
#         print(f"[GDRIVE_SERVICE] Placeholder created with GDrive ID: {gdrive_id}")

#         # Step 2: Initiate a resumable session to UPDATE this placeholder file.
#         # We need to use a lower-level, authorized HTTP session for this.
#         from google.auth.transport.requests import AuthorizedSession
        
#         # Use the credentials object directly to create the session.
#         authed_session = AuthorizedSession(creds)
        
#         # The request to initiate an upload to an existing file is a PATCH request.
#         # We don't need to send any body, just the correct URL and uploadType.
#         headers = { "Content-Length": "0" }
        
#         print(f"[GDRIVE_SERVICE] Initiating resumable session for GDrive ID: {gdrive_id}...")
#         response = authed_session.patch(
#             f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
#             headers=headers
#         )
        
#         # This will raise an error if Google responds with a 4xx or 5xx status.
#         response.raise_for_status()

#         # The resumable upload URL is in the 'Location' header of the successful response.
#         upload_url = response.headers['Location']
#         print(f"[GDRIVE_SERVICE] Resumable session created successfully.")
        
#         return gdrive_id, upload_url

#     except HttpError as e:
#         print(f"!!! A Google API HTTP Error occurred: {e.content}")
#         raise e
#     except Exception as e:
#         print(f"!!! An unexpected error occurred in create_resumable_upload_session: {e}")
#         raise e


# # --- The rest of the functions are for future use if needed ---

# def download_file_from_gdrive(file_id: str) -> io.BytesIO:
#     service = get_drive_service()
#     request = service.files().get_media(fileId=file_id)
#     fh = io.BytesIO()
#     # Using a BufferedReader for efficiency
#     downloader = io.BufferedReader(request)
#     while True:
#         chunk = downloader.read(1024 * 1024) # Read in 1MB chunks
#         if not chunk:
#             break
#         fh.write(chunk)
#     fh.seek(0)
#     return fh

# def delete_file_from_gdrive(file_id: str):
#     try:
#         service = get_drive_service()
#         service.files().delete(fileId=file_id).execute()
#         print(f"Successfully deleted file {file_id} from Google Drive.")
#     except HttpError as error:
#         print(f"An error occurred while deleting from GDrive: {error}")



import asyncio
from google.oauth2 import service_account
from fastapi.concurrency import run_in_threadpool   
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from app.core.config import settings
import io
from typing import AsyncGenerator
import os
import threading
from fastapi import BackgroundTasks
from googleapiclient.http import MediaIoBaseDownload


SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service(creds: service_account.Credentials = None):
    """Initializes and returns the Google Drive service client."""
    if not creds:
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def create_resumable_upload_session(filename: str, creds: service_account.Credentials) -> (str, str):
    """
    Creates a 0-byte placeholder file on Google Drive to get a stable file ID,
    then initiates a resumable upload session to update that file.
    """
    try:
        service = get_drive_service(creds)
        file_metadata = {
            'name': filename,
            'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
        }
        print("[GDRIVE_SERVICE] Creating placeholder file...")
        placeholder_file = service.files().create(body=file_metadata, fields='id').execute()
        gdrive_id = placeholder_file.get('id')
        if not gdrive_id:
            raise Exception("Failed to create placeholder file in Google Drive.")
        print(f"[GDRIVE_SERVICE] Placeholder created with GDrive ID: {gdrive_id}")

        from google.auth.transport.requests import AuthorizedSession
        authed_session = AuthorizedSession(creds)
        
        headers = { "Content-Length": "0" }
        print(f"[GDRIVE_SERVICE] Initiating resumable session for GDrive ID: {gdrive_id}...")
        response = authed_session.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
            headers=headers
        )
        response.raise_for_status()
        upload_url = response.headers['Location']
        print(f"[GDRIVE_SERVICE] Resumable session created successfully.")
        return gdrive_id, upload_url

    except HttpError as e:
        print(f"!!! A Google API HTTP Error occurred: {e.content}")
        raise e
    except Exception as e:
        print(f"!!! An unexpected error occurred in create_resumable_upload_session: {e}")
        raise e

# # --- NEW FUNCTION FOR STREAMING DOWNLOADS ---
# def stream_gdrive_file(file_id: str) -> Generator[bytes, None, None]:
#     """
#     Downloads a file from Google Drive and yields it in chunks.
#     This is memory-efficient and suitable for FastAPI's StreamingResponse.
#     """
#     try:
#         service = get_drive_service()
#         request = service.files().get_media(fileId=file_id)
        
#         # Use a downloader that supports chunked reading
#         downloader = io.BufferedReader(request)
        
#         while True:
#             # Read a chunk of data (e.g., 4MB)
#             chunk = downloader.read(4 * 1024 * 1024)
#             if not chunk:
#                 # End of file
#                 break
#             # Yield the chunk to the streaming response
#             yield chunk
#         print(f"[GDRIVE_SERVICE] Finished streaming file {file_id}")

#     except HttpError as error:
#         print(f"!!! An error occurred while streaming from GDrive: {error}")
#         # You might want to handle this more gracefully, but for now, it will stop the stream.
#         return


# # --- THIS IS THE NEW, DEFINITIVE STREAMING FUNCTION ---
# async def stream_gdrive_file(file_id: str) -> AsyncGenerator[bytes, None]:
#     """
#     Asynchronously streams a file from Google Drive using a dedicated thread
#     and an OS pipe to bridge the sync/async gap safely.
#     """
#     # Create a low-level OS pipe. This is how the thread will send data
#     # back to our async function.
#     read_fd, write_fd = os.pipe()

#     def download_in_thread():
#         """
#         This function runs in a separate thread. It performs the standard,
#         blocking download and writes the data to the pipe.
#         """
#         try:
#             print("[DOWNLOAD_THREAD] Starting download...")
#             service = get_drive_service()
#             request = service.files().get_media(fileId=file_id)
#             downloader = io.BufferedReader(request)
            
#             with os.fdopen(write_fd, 'wb') as writer:
#                 while True:
#                     chunk = downloader.read(4 * 1024 * 1024)
#                     if not chunk:
#                         break
#                     writer.write(chunk)
            
#             print("[DOWNLOAD_THREAD] Download finished.")
#         except Exception as e:
#             print(f"!!! [DOWNLOAD_THREAD] Error: {e}")
#         # The 'with' statement automatically closes the writer end of the pipe,
#         # which signals the end of the stream to the reader.

#     # Start the download function in a separate, daemonized thread.
#     download_thread = threading.Thread(target=download_in_thread, daemon=True)
#     download_thread.start()

#     # Our main async function now reads from the other end of the pipe.
#     loop = asyncio.get_event_loop()
#     with os.fdopen(read_fd, 'rb') as reader:
#         while True:
#             # Use run_in_executor to read from the blocking pipe without
#             # blocking the main event loop.
#             chunk = await loop.run_in_executor(None, reader.read, 4 * 1024 * 1024)
#             if not chunk:
#                 break
#             yield chunk
            
#     print(f"[GDRIVE_SERVICE] Finished streaming file {file_id}")
#     download_thread.join() # Wait for the thread to finish cleanly.
    


# --- THIS IS THE FINAL, CORRECTED STREAMING FUNCTION ---
async def stream_gdrive_file(file_id: str) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously streams a file from Google Drive using a dedicated thread
    and an OS pipe to bridge the sync/async gap safely.
    """
    read_fd, write_fd = os.pipe()

    def download_in_thread():
        """
        This function runs in a separate thread. It performs the standard,
        blocking download using the correct Google API client methods and,
        crucially, the correct USER credentials.
        """
        # --- FIX: Robustly handle cleanup in case of an error ---
        writer = None
        try:
            print("[DOWNLOAD_THREAD] Starting download...")

            # --- FIX: Authenticate as the USER using the OAuth 2.0 Refresh Token ---
            # This is the same method used successfully by your other tasks.
            user_creds = Credentials.from_authorized_user_info(
                info={
                    "client_id": settings.OAUTH_CLIENT_ID,
                    "client_secret": settings.OAUTH_CLIENT_SECRET,
                    "refresh_token": settings.OAUTH_REFRESH_TOKEN,
                },
                scopes=SCOPES
            )
            
            # Build the service using the user's credentials, NOT the default service account.
            service = get_drive_service(creds=user_creds)
            # --- END OF AUTHENTICATION FIX ---

            request = service.files().get_media(fileId=file_id)
            
            # This is the writer end of our in-memory pipe
            writer = io.FileIO(write_fd, 'wb')
            
            # This is the official Google API object for handling media downloads
            downloader = MediaIoBaseDownload(writer, request)
            
            done = False
            while not done:
                # The .next_chunk() method downloads a piece of the file
                # and writes it directly to our 'writer' object (the pipe).
                status, done = downloader.next_chunk()
                if status:
                    print(f"[DOWNLOAD_THREAD] Downloaded {int(status.progress() * 100)}%.")

            print("[DOWNLOAD_THREAD] Download finished.")
        except Exception as e:
            # This will now correctly log authentication errors or any other issues.
            print(f"!!! [DOWNLOAD_THREAD] Error: {e}")
        finally:
            # --- FIX: Ensure the writer is closed only if it was created ---
            # This prevents the UnboundLocalError.
            if writer:
                writer.close()

    # Start the download function in a separate, daemonized thread.
    download_thread = threading.Thread(target=download_in_thread, daemon=True)
    download_thread.start()

    # Our main async function now reads from the other end of the pipe.
    loop = asyncio.get_event_loop()
    reader = io.FileIO(read_fd, 'rb')
    
    while True:
        # Use run_in_executor to read from the blocking pipe
        chunk = await loop.run_in_executor(None, reader.read, 4 * 1024 * 1024)
        if not chunk:
            break
        yield chunk
            
    print(f"[GDRIVE_SERVICE] Finished streaming file {file_id}")
    download_thread.join() # Wait for the thread to finish cleanly.
    reader.close()
    
# --- NEW FUNCTION FOR DELETION USING OAUTH REFRESH TOKEN ---
def delete_file_with_refresh_token(file_id: str):
    """
    Deletes a file from Google Drive using a user's OAuth 2.0 refresh token.
    This is more robust for permissions than a service account sometimes.
    """
    try:
        print(f"[GDRIVE_DELETER] Attempting to delete file {file_id} using user credentials.")
        
        # 1. Build credentials from the stored refresh token
        user_creds = Credentials.from_authorized_user_info(
            info={
                "client_id": settings.OAUTH_CLIENT_ID,
                "client_secret": settings.OAUTH_CLIENT_SECRET,
                "refresh_token": settings.OAUTH_REFRESH_TOKEN,
            },
            scopes=SCOPES
        )

        # 2. Build the service with the user's credentials
        service = get_drive_service(creds=user_creds)

        # 3. Execute the deletion
        service.files().delete(fileId=file_id).execute()
        
        print(f"[GDRIVE_DELETER] Successfully deleted file {file_id}.")

    except HttpError as e:
        print(f"!!! [GDRIVE_DELETER] Google API HTTP Error during deletion: {e.content}")
        # We don't re-raise here to prevent the whole task from failing if only deletion fails
    except Exception as e:
        print(f"!!! [GDRIVE_DELETER] An unexpected error occurred during deletion: {e}")
        
        
        
# ... (at the end of the file, after delete_file_with_refresh_token)

def download_file_from_gdrive(gdrive_id: str) -> io.BytesIO:
    """
    Downloads a file from Google Drive into an in-memory BytesIO object.
    Uses the OAuth 2.0 refresh token to ensure correct permissions.
    """
    try:
        print(f"[GDRIVE_DOWNLOADER] Downloading file {gdrive_id} using user credentials.")
        
        # 1. Build credentials from the stored refresh token
        user_creds = Credentials.from_authorized_user_info(
            info={
                "client_id": settings.OAUTH_CLIENT_ID,
                "client_secret": settings.OAUTH_CLIENT_SECRET,
                "refresh_token": settings.OAUTH_REFRESH_TOKEN,
            },
            scopes=SCOPES
        )

        # 2. Build the service with the user's credentials
        service = get_drive_service(creds=user_creds)
        
        # 3. Prepare the download request
        request = service.files().get_media(fileId=gdrive_id)
        
        # 4. Download the content into an in-memory binary stream
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"[GDRIVE_DOWNLOADER] Download progress: {int(status.progress() * 100)}%.")
        
        # Reset the stream's position to the beginning so it can be read
        fh.seek(0)
        print(f"[GDRIVE_DOWNLOADER] File {gdrive_id} downloaded successfully.")
        return fh

    except HttpError as e:
        print(f"!!! [GDRIVE_DOWNLOADER] Google API HTTP Error during download: {e.content}")
        raise e
    except Exception as e:
        print(f"!!! [GDRIVE_DOWNLOADER] An unexpected error occurred during download: {e}")
        raise