# # server/backend/app/api/v1/routes_upload.py (Completely Updated)

# from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Body
# from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation
# from app.models.user import UserInDB
# from app.services.auth_service import get_current_user, get_current_user_optional
# from app.db.mongodb import db
# from app.tasks.file_transfer_task import transfer_gdrive_to_telegram
# from googleapiclient.errors import HttpError
# from app.services import google_drive_service
# import uuid
# from typing import Optional

# router = APIRouter()

# # --- NEW INITIATE ENDPOINT ---
# @router.post("/upload/initiate")
# async def initiate_upload(
#     filename: str = Body(...),
#     filesize: int = Body(...),
#     content_type: str = Body(...), # We don't use content_type anymore but can keep it
#     current_user: Optional[UserInDB] = Depends(get_current_user_optional)
# ):
#     # 1. Check file size limits
#     limit_gb = 15 if current_user else 5
#     if filesize > limit_gb * 1024 * 1024 * 1024:
#         raise HTTPException(status_code=413, detail=f"File size exceeds {limit_gb}GB limit.")

#     # 2. Create the resumable session with improved error handling
#     try:
#         # The service no longer needs filesize or content_type for initiation
#         gdrive_id, upload_url = google_drive_service.create_resumable_upload_session(filename)

#     # --- ADDED DETAILED EXCEPTION HANDLING ---
#     except HttpError as e:
#         # This will catch errors from the Google API client library
#         print("!!! GOOGLE API HTTP ERROR !!!")
#         print(f"Error details: {e.content}")
#         error_content = e.content.decode('utf-8')
#         raise HTTPException(
#             status_code=e.resp.status,
#             detail=f"Google API Error: {error_content}"
#         )
#     except Exception as e:
#         # This will catch other unexpected errors
#         print(f"!!! UNEXPECTED SERVER ERROR: {e} !!!")
#         raise HTTPException(
#             status_code=500,
#             detail=f"An unexpected error occurred on the server: {str(e)}"
#         )

#     # 3. Create initial record in MongoDB
#     file_id = str(uuid.uuid4())
#     file_meta = FileMetadataCreate(
#         _id=file_id,
#         filename=filename,
#         size_bytes=filesize,
#         content_type=content_type,
#         gdrive_id=gdrive_id,
#         owner_id=current_user.id if current_user else None
#     )
#     db.files.insert_one(file_meta.model_dump(by_alias=True))

#     return {"file_id": file_id, "upload_url": upload_url}


# # --- NEW FINALIZE ENDPOINT ---
# @router.post("/upload/finalize/{file_id}")
# async def finalize_upload(file_id: str, background_tasks: BackgroundTasks):
#     file_doc = db.files.find_one({"_id": file_id})
#     if not file_doc:
#         raise HTTPException(status_code=404, detail="File ID not found.")

#     # Here you could add a check against GDrive to confirm the file exists and size matches, for extra security.
    
#     # Start the background transfer task
#     background_tasks.add_task(transfer_gdrive_to_telegram, file_id)

#     return {"message": "Upload finalized. Transfer to permanent storage has begun.", "download_link": f"/download/{file_id}"}


# # --- These routes remain mostly the same ---
# @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# async def get_file_metadata(file_id: str):
#     file_doc = db.files.find_one({"_id": file_id})
#     if not file_doc:
#         raise HTTPException(status_code=404, detail="File not found")
#     return FileMetadataInDB(**file_doc)

# @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
#     files = db.files.find({"owner_id": current_user.id})
#     return [FileMetadataInDB(**f) for f in files]

# @router.get("/download/{file_id}")
# async def download_file(file_id: str):
#     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")


from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation, InitiateUploadRequest, UploadStatus
from app.models.user import UserInDB
# from app.services.auth_service import get_optional_current_user # We use the optional one now
from app.db.mongodb import db
# We will use this in the next steps, but good to have the import now
# from app.tasks.file_transfer_task import transfer_gdrive_to_telegram
from app.services import google_drive_service
import uuid
from typing import Optional
from pathlib import Path # Add this import for path handling
from app.services.auth_service import try_get_current_user, get_current_user
from app.services.auth_service import get_current_user_optional
router = APIRouter()

# Define the directory for temporary uploads
UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True) # Ensure the directory exists

@router.post("/upload/initiate", response_model=dict)
async def initiate_upload(
    request: InitiateUploadRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user_optional) 
):
    """
    First step of the upload process.
    The frontend announces its intent to upload a file.
    The backend generates a unique ID for the session and creates a DB record.
    """
    file_id = str(uuid.uuid4())
    file_meta = FileMetadataCreate(
        _id=file_id,
        filename=request.filename,
        size_bytes=request.size,
        content_type=request.content_type,
        owner_id=current_user.id if current_user else None,
        status=UploadStatus.PENDING
    )
    db.files.insert_one(file_meta.model_dump(by_alias=True))
    return {"file_id": file_id}


# THIS IS THE NEW WEBSOCKET ENDPOINT
@router.websocket("/ws/upload/{file_id}")
async def websocket_upload(websocket: WebSocket, file_id: str):
    """
    Handles the high-speed file upload via a WebSocket connection.
    Receives binary chunks and writes them to a temporary file.
    """
    await websocket.accept()
    
    # Check if the file_id is valid
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        print(f"Invalid file_id received: {file_id}")
        await websocket.close(code=1008) # Policy Violation
        return

    file_path = UPLOAD_DIR / f"{file_id}.tmp"
    bytes_written = 0
    
    # Update status in DB to show that the upload to the server has started
    db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_SERVER}})

    try:
        with open(file_path, "wb") as f:
            while True:
                # Receive data from the client
                data = await websocket.receive_bytes()
                f.write(data)
                bytes_written += len(data)

    except WebSocketDisconnect:
        print(f"Client disconnected. Upload for {file_id} finished.")
        # Final status update once the client disconnects
        # Here we can also verify if bytes_written matches the expected size
        expected_size = file_doc.get("size_bytes", 0)
        if bytes_written == expected_size:
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
            print(f"File {file_id} successfully saved to {file_path}")
        else:
            db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
            print(f"File {file_id} upload failed. Expected {expected_size}, got {bytes_written}.")
            file_path.unlink() # Delete partial file
    except Exception as e:
        # Handle other potential errors
        print(f"An error occurred during upload for {file_id}: {e}")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        if file_path.exists():
            file_path.unlink() # Clean up


# We are keeping the old routes for now, but they will be replaced.
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