# server/backend/app/api/v1/routes_upload.py (Completely Updated)

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Body
from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation
from app.models.user import UserInDB
from app.services.auth_service import get_current_user, get_current_user_optional
from app.db.mongodb import db
from app.tasks.file_transfer_task import transfer_gdrive_to_telegram
from googleapiclient.errors import HttpError
from app.services import google_drive_service
import uuid
from typing import Optional

router = APIRouter()

# --- NEW INITIATE ENDPOINT ---
@router.post("/upload/initiate")
async def initiate_upload(
    filename: str = Body(...),
    filesize: int = Body(...),
    content_type: str = Body(...), # We don't use content_type anymore but can keep it
    current_user: Optional[UserInDB] = Depends(get_current_user_optional)
):
    # 1. Check file size limits
    limit_gb = 15 if current_user else 5
    if filesize > limit_gb * 1024 * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File size exceeds {limit_gb}GB limit.")

    # 2. Create the resumable session with improved error handling
    try:
        # The service no longer needs filesize or content_type for initiation
        gdrive_id, upload_url = google_drive_service.create_resumable_upload_session(filename)

    # --- ADDED DETAILED EXCEPTION HANDLING ---
    except HttpError as e:
        # This will catch errors from the Google API client library
        print("!!! GOOGLE API HTTP ERROR !!!")
        print(f"Error details: {e.content}")
        error_content = e.content.decode('utf-8')
        raise HTTPException(
            status_code=e.resp.status,
            detail=f"Google API Error: {error_content}"
        )
    except Exception as e:
        # This will catch other unexpected errors
        print(f"!!! UNEXPECTED SERVER ERROR: {e} !!!")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred on the server: {str(e)}"
        )

    # 3. Create initial record in MongoDB
    file_id = str(uuid.uuid4())
    file_meta = FileMetadataCreate(
        _id=file_id,
        filename=filename,
        size_bytes=filesize,
        content_type=content_type,
        gdrive_id=gdrive_id,
        owner_id=current_user.id if current_user else None
    )
    db.files.insert_one(file_meta.model_dump(by_alias=True))

    return {"file_id": file_id, "upload_url": upload_url}


# --- NEW FINALIZE ENDPOINT ---
@router.post("/upload/finalize/{file_id}")
async def finalize_upload(file_id: str, background_tasks: BackgroundTasks):
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File ID not found.")

    # Here you could add a check against GDrive to confirm the file exists and size matches, for extra security.
    
    # Start the background transfer task
    background_tasks.add_task(transfer_gdrive_to_telegram, file_id)

    return {"message": "Upload finalized. Transfer to permanent storage has begun.", "download_link": f"/download/{file_id}"}


# --- These routes remain mostly the same ---
@router.get("/files/{file_id}", response_model=FileMetadataInDB)
async def get_file_metadata(file_id: str):
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    return FileMetadataInDB(**file_doc)

@router.get("/files/me/history", response_model=list[FileMetadataInDB])
async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
    files = db.files.find({"owner_id": current_user.id})
    return [FileMetadataInDB(**f) for f in files]

@router.get("/download/{file_id}")
async def download_file(file_id: str):
    raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")