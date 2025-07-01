from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.db.mongodb import db
from app.models.file import FileMetadataInDB
from app.services import google_drive_service

router = APIRouter()

@router.get("/files/{file_id}/meta", response_model=FileMetadataInDB)
async def get_file_metadata(file_id: str):
    """
    Endpoint to fetch just the metadata for a file.
    The download page will call this to display the file name and size.
    """
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    
    return file_doc

@router.get("/download/stream/{file_id}")
async def stream_download(file_id: str):
    """
    This is the main download endpoint. It streams the file from 
    Google Drive directly to the user.
    """
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc or 'gdrive_id' not in file_doc:
        raise HTTPException(status_code=404, detail="File not found or not yet uploaded to Drive")

    gdrive_id = file_doc['gdrive_id']
    filename = file_doc['filename']

    # Set headers to tell the browser this is a file download
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }

    # Stream the response
    return StreamingResponse(
        google_drive_service.stream_gdrive_file(gdrive_id),
        headers=headers
    )