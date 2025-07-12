"""
Download routes for DirectDrive backend.
MVP version with Hetzner Storage-Box only (no Google Drive or Telegram).
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from urllib.parse import quote
import os

from app.db.mongodb import db
from app.services.hetzner_service import hetzner_client
from app.models.file import FileMetadataInDB

router = APIRouter()

@router.get(
    "/files/{file_id}/meta",
    response_model=FileMetadataInDB,
    summary="Get File Metadata",
    tags=["Download"]
)
def get_file_metadata(file_id: str):
    """
    Retrieves the metadata for a specific file, such as its name and size.
    """
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    return file_doc

@router.get(
    "/download/stream/{file_id}",
    summary="Stream File for Download",
    tags=["Download"]
)
async def stream_download(file_id: str, request: Request):
    """
    Provides a direct download link for a file.
    This endpoint intelligently streams the file from Hetzner Storage-Box.
    """
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    filename = file_doc.get("filename", "download")
    filesize = file_doc.get("size_bytes", 0)
    remote_path = file_doc.get("remote_path")
    
    if not remote_path:
        raise HTTPException(status_code=404, detail="File remote path not found")

    # For local testing, stream from the local storage directory
    async def content_streamer():
        print(f"[STREAMER] Starting stream for '{filename}' from Hetzner.")
        try:
            # For local testing, read from the local storage directory
            local_path = os.path.join(hetzner_client.local_storage_dir, remote_path)
            if not os.path.exists(local_path):
                raise ValueError(f"File not found at {local_path}")
                
            # Stream the file in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(local_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    yield chunk
                    
            print(f"[STREAMER] Finished streaming '{filename}' successfully.")
        except Exception as e:
            print(f"!!! [STREAMER] An error occurred during file stream for {file_id}: {e}")

    headers = {
        "Content-Length": str(filesize),
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
    }

    return StreamingResponse(
        content=content_streamer(),
        media_type="application/octet-stream",
        headers=headers
    )

# Add a direct file download endpoint for local testing
@router.get(
    "/files/download/{remote_path:path}",
    summary="Direct File Download",
    tags=["Download"]
)
async def direct_download(remote_path: str):
    """
    Provides a direct download link for a file using its remote path.
    This is used for local testing to simulate the Cloudflare Worker.
    """
    try:
        # Find the file in the database by remote_path
        file_doc = db.files.find_one({"remote_path": remote_path})
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found in database")
            
        filename = file_doc.get("filename", "download")
        filesize = file_doc.get("size_bytes", 0)
        
        # For local testing, read from the local storage directory
        local_path = os.path.join(hetzner_client.local_storage_dir, remote_path)
        if not os.path.exists(local_path):
            raise HTTPException(status_code=404, detail=f"File not found at {local_path}")
            
        # Stream the file in chunks
        async def content_streamer():
            chunk_size = 1024 * 1024  # 1MB chunks
            with open(local_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    yield chunk
        
        headers = {
            "Content-Length": str(filesize),
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
        }
        
        return StreamingResponse(
            content=content_streamer(),
            media_type="application/octet-stream",
            headers=headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error streaming file: {str(e)}")
