"""
Upload routes for DirectDrive backend.
MVP version with Hetzner Storage-Box only (no Google Drive or Telegram).
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from app.models.file import FileMetadataCreate, FileMetadataInDB, UploadStatus, StorageLocation
from app.models.user import UserInDB
from app.db.mongodb import db
from app.services.auth_service import get_current_user_optional, get_current_user
from app.services.hetzner_service import hetzner_client
from app.core.config import settings

router = APIRouter()

@router.post("/upload", response_model=dict)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: Optional[UserInDB] = Depends(get_current_user_optional)
):
    """
    Upload a file using multipart/form-data directly to Hetzner Storage-Box.
    Streams the file to avoid memory issues with large files.
    
    Args:
        request: The FastAPI request object
        file: The uploaded file
        current_user: Optional authenticated user
        
    Returns:
        Dict with file_id and share_url
    """
    try:
        # Generate a unique file ID
        file_id = str(uuid.uuid4())
        
        # Generate a unique remote path using the original filename's extension
        remote_path = hetzner_client.generate_remote_path(file.filename)
        
        # Create the initial database record
        file_meta = FileMetadataCreate(
            _id=file_id,
            filename=file.filename,
            size_bytes=0,  # Will be updated after upload
            content_type=file.content_type,
            owner_id=current_user.id if current_user else None,
            status=UploadStatus.UPLOADING,
            remote_path=remote_path
        )
        db.files.insert_one(file_meta.model_dump(by_alias=True))
        
        # Stream the file to Hetzner Storage-Box
        success = await hetzner_client.upload_file_async(
            file_stream=file.file,
            remote_path=remote_path
        )
        
        if not success:
            # Update status to failed if upload fails
            db.files.update_one(
                {"_id": file_id},
                {"$set": {"status": UploadStatus.FAILED}}
            )
            raise HTTPException(status_code=500, detail="Failed to upload file to storage")
        
        # Get the final file size
        size = file.file.tell()
        
        # Update the file record with the final size and status
        db.files.update_one(
            {"_id": file_id},
            {"$set": {
                "size_bytes": size,
                "status": UploadStatus.COMPLETED,
                "storage_location": StorageLocation.HETZNER
            }}
        )
        
        # For local testing, use local download endpoint instead of Cloudflare Worker domain
        # Check if we're in a local development environment
        if settings.PORT != 443:  # Not production
            # Hardcode port 5002 since that's what the server is actually running on
            share_url = f"http://localhost:5002/api/v1/files/download/{remote_path}"
        else:
            # Production URL using Cloudflare Worker domain
            share_url = f"https://{settings.DOWNLOAD_DOMAIN}/{remote_path}"
        
        return {
            "file_id": file_id,
            "share_url": share_url
        }
        
    except Exception as e:
        print(f"Error during file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/files/{file_id}", response_model=FileMetadataInDB)
def get_file_metadata(file_id: str):
    """Get metadata for a specific file"""
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    return file_doc

@router.get("/files", response_model=list[FileMetadataInDB])
def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
    """Get a user's file upload history"""
    files = list(db.files.find({"owner_id": current_user.id}))
    return files

# Download endpoint is now in routes_download.py
