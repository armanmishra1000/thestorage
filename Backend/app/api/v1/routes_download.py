from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.db.mongodb import db
from app.models.file import FileMetadataInDB
from app.services import google_drive_service
from app.services import telegram_service


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
    This is the main download endpoint. It intelligently streams the file 
    from its current location (Google Drive or Telegram).
    """
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")

    filename = file_doc['filename']
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}

    # --- THE NEW INTELLIGENT LOGIC ---
    storage_location = file_doc.get("storage_location")

    if storage_location == "gdrive":
        print(f"Streaming {file_id} from Google Drive...")
        gdrive_id = file_doc.get("gdrive_id")
        if not gdrive_id:
            raise HTTPException(status_code=404, detail="File is in GDrive but ID is missing.")
        return StreamingResponse(google_drive_service.stream_gdrive_file(gdrive_id), headers=headers)

    elif storage_location == "telegram":
        print(f"Streaming {file_id} from Telegram...")
        file_ids = file_doc.get("telegram_file_ids")
        if not file_ids:
             raise HTTPException(status_code=404, detail="File is in Telegram but IDs are missing.")
        return StreamingResponse(telegram_service.stream_file_from_telegram(file_ids), headers=headers)
        
    else:
        # Handle cases where the file is still uploading or has failed
        raise HTTPException(status_code=404, detail="File is not yet available for download. Please try again later.")