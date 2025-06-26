# server/backend/app/services/google_drive_service.py (Corrected)

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import settings
import io

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Initializes and returns the Google Drive service client."""
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

def create_resumable_upload_session(filename: str) -> (str, str):
    """
    Creates a 0-byte placeholder file on Google Drive to get a stable file ID,
    then initiates a resumable upload session to update that file.
    Returns a tuple of (gdrive_id, upload_url).
    """
    service = get_drive_service()
    
    # Step 1: Create a 0-byte placeholder file with the final name and location.
    # This gives us a permanent file ID before the upload even starts.
    file_metadata = {
        'name': filename,
        'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
    }
    print(f"Creating placeholder file '{filename}' in GDrive folder '{settings.GOOGLE_DRIVE_FOLDER_ID}'...")
    placeholder_file = service.files().create(body=file_metadata, fields='id').execute()
    gdrive_id = placeholder_file.get('id')
    print(f"Placeholder created with GDrive ID: {gdrive_id}")

    # Step 2: Initiate a resumable session to UPDATE this placeholder file.
    # We use the 'google.auth.transport' for direct HTTP request control.
    from google.auth.transport.requests import AuthorizedSession
    authed_session = AuthorizedSession(service._credentials)

    # The key change is here: The initiation request for an UPDATE is a simple PATCH
    # with no special X-Upload headers.
    headers = {
        "Content-Length": "0" # We are not sending any metadata in the patch body itself.
    }
    
    print(f"Initiating resumable session for GDrive ID: {gdrive_id}...")
    response = authed_session.patch(
        f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
        headers=headers
    )
    
    # Ensure the request to Google was successful
    response.raise_for_status()

    upload_url = response.headers['Location']
    print(f"Resumable session created. Upload URL: {upload_url}")
    
    return gdrive_id, upload_url


def download_file_from_gdrive(file_id: str) -> io.BytesIO:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = io.BufferedReader(request)
    while True:
        chunk = downloader.read(1024 * 1024) # Read in 1MB chunks
        if not chunk:
            break
        fh.write(chunk)
    fh.seek(0)
    return fh

def delete_file_from_gdrive(file_id: str):
    try:
        service = get_drive_service()
        service.files().delete(fileId=file_id).execute()
        print(f"Successfully deleted file {file_id} from Google Drive.")
    except HttpError as error:
        print(f"An error occurred while deleting from GDrive: {error}")
        
        
def create_resumable_upload_session(filename: str) -> (str, str):
    """
    Creates a 0-byte placeholder file on Google Drive to get a stable file ID,
    then initiates a resumable upload session to update that file.
    Returns a tuple of (gdrive_id, upload_url).
    """
    # Create the credentials object
    creds = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
        
    # Build the high-level service object using the credentials
    service = build('drive', 'v3', credentials=creds)
    
    # Step 1: Create a 0-byte placeholder file. This part is working correctly.
    file_metadata = {
        'name': filename,
        'parents': [settings.GOOGLE_DRIVE_FOLDER_ID]
    }
    print(f"Creating placeholder file '{filename}' in GDrive folder '{settings.GOOGLE_DRIVE_FOLDER_ID}'...")
    placeholder_file = service.files().create(body=file_metadata, fields='id').execute()
    gdrive_id = placeholder_file.get('id')
    print(f"Placeholder created with GDrive ID: {gdrive_id}")

    # Step 2: Initiate a resumable session.
    from google.auth.transport.requests import AuthorizedSession
    
    # --- THIS IS THE FIX ---
    # Use the 'creds' object we already have, NOT the 'service' object.
    authed_session = AuthorizedSession(creds)
    # --- END OF FIX ---

    headers = {
        "Content-Length": "0"
    }
    
    print(f"Initiating resumable session for GDrive ID: {gdrive_id}...")
    response = authed_session.patch(
        f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
        headers=headers
    )
    
    response.raise_for_status()

    upload_url = response.headers['Location']
    print(f"Resumable session created. Upload URL: {upload_url}")
    
    return gdrive_id, upload_url