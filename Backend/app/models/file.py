# In file: Backend/app/models/file.py

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import datetime

# --- MODIFIED: Simplified for Hetzner WebDAV storage ---
class StorageLocation(str, Enum):
    HETZNER = "hetzner"

# --- MODIFIED: Simplified to reflect direct upload flow ---
class UploadStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class FileMetadataBase(BaseModel):
    filename: str
    size_bytes: int
    content_type: str

class FileMetadataCreate(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    # The storage location is now Hetzner WebDAV
    storage_location: StorageLocation = StorageLocation.HETZNER
    status: UploadStatus = UploadStatus.PENDING
    remote_path: Optional[str] = None  # Path on Hetzner Storage-Box
    owner_id: Optional[str] = None

class FileMetadataInDB(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime
    storage_location: StorageLocation
    status: UploadStatus
    remote_path: Optional[str] = None  # Path on Hetzner Storage-Box
    owner_id: Optional[str] = None

    class Config:
        populate_by_name = True
        from_attributes = True

class InitiateUploadRequest(BaseModel):
    filename: str
    size: int
    content_type: str