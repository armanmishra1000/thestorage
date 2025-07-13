"""
Upload routes for DirectDrive backend.
MVP version with Hetzner Storage-Box only (no Google Drive or Telegram).
"""
import uuid
import os
import time
import psutil
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from app.models.file import FileMetadataCreate, FileMetadataInDB, UploadStatus, StorageLocation
from app.models.user import UserInDB
from app.db.mongodb import db
from app.services.auth_service import get_current_user_optional, get_current_user
from app.services.hetzner_service import hetzner_client
from app.core.config import settings
from app.utils.logging_utils import log_file_operation, timed_api_endpoint, log_api_call, get_memory_usage

router = APIRouter()

@router.post("/upload", response_model=dict)
@timed_api_endpoint
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
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Initial memory usage
    initial_memory = get_memory_usage()
    
    try:
        # Log upload start
        log_file_operation(
            operation_type="upload_start",
            file_info={
                "filename": file.filename,
                "content_type": file.content_type,
                "client_ip": client_ip
            },
            extra_info={
                "initial_memory": initial_memory
            }
        )
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
        
        # Record pre-upload memory
        pre_upload_memory = get_memory_usage()
        pre_upload_time = time.time()
        
        # Stream the file to Hetzner Storage-Box
        success = await hetzner_client.upload_file_async(
            file_stream=file.file,
            remote_path=remote_path,
            file_id=file_id  # Pass file_id for logging in the service
        )
        
        # Calculate upload duration and post-upload memory
        upload_duration = time.time() - pre_upload_time
        post_upload_memory = get_memory_usage()
        
        # Log upload completion
        log_file_operation(
            operation_type="upload_complete",
            file_info={
                "file_id": file_id,
                "filename": file.filename,
                "remote_path": remote_path,
                "content_type": file.content_type
            },
            extra_info={
                "upload_duration_seconds": upload_duration,
                "pre_upload_memory": pre_upload_memory,
                "post_upload_memory": post_upload_memory,
                "success": success
            }
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
        # In production (Render), the environment variable 'RENDER' is set
        if os.environ.get('RENDER', '').lower() == 'true':
            # Production URL using Cloudflare Worker domain
            share_url = f"https://{settings.DOWNLOAD_DOMAIN}/{remote_path}"
        else:
            # Local development URL
            # Hardcode port 5002 since that's what the server is actually running on locally
            share_url = f"http://localhost:5002/api/v1/files/download/{remote_path}"
        
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
