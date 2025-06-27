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
    try:
        # Create the credentials object from the service account file
        creds = service_account.Credentials.from_service_account_file(
            settings.GOOGLE_APPLICATION_CREDENTIALS, scopes=SCOPES)
            
        # Build the high-level service object for simple operations
        service = build('drive', 'v3', credentials=creds)
        
        # Step 1: Create a 0-byte placeholder file. This gives us a permanent file ID.
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

        # Step 2: Initiate a resumable session to UPDATE this placeholder file.
        # We need to use a lower-level, authorized HTTP session for this.
        from google.auth.transport.requests import AuthorizedSession
        
        # Use the credentials object directly to create the session.
        authed_session = AuthorizedSession(creds)
        
        # The request to initiate an upload to an existing file is a PATCH request.
        # We don't need to send any body, just the correct URL and uploadType.
        headers = { "Content-Length": "0" }
        
        print(f"[GDRIVE_SERVICE] Initiating resumable session for GDrive ID: {gdrive_id}...")
        response = authed_session.patch(
            f"https://www.googleapis.com/upload/drive/v3/files/{gdrive_id}?uploadType=resumable",
            headers=headers
        )
        
        # This will raise an error if Google responds with a 4xx or 5xx status.
        response.raise_for_status()

        # The resumable upload URL is in the 'Location' header of the successful response.
        upload_url = response.headers['Location']
        print(f"[GDRIVE_SERVICE] Resumable session created successfully.")
        
        return gdrive_id, upload_url

    except HttpError as e:
        print(f"!!! A Google API HTTP Error occurred: {e.content}")
        raise e
    except Exception as e:
        print(f"!!! An unexpected error occurred in create_resumable_upload_session: {e}")
        raise e


# --- The rest of the functions are for future use if needed ---

def download_file_from_gdrive(file_id: str) -> io.BytesIO:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    # Using a BufferedReader for efficiency
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