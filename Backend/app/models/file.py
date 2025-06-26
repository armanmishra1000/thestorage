from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import datetime

class StorageLocation(str, Enum):
    GDRIVE = "gdrive"
    TELEGRAM = "telegram"

class FileMetadataBase(BaseModel):
    filename: str
    size_bytes: int
    content_type: str

class FileMetadataCreate(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    storage_location: StorageLocation = StorageLocation.GDRIVE
    gdrive_id: str
    owner_id: Optional[str] = None # For registered users

class FileMetadataInDB(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime
    storage_location: StorageLocation
    gdrive_id: Optional[str] = None
    telegram_message_ids: Optional[List[int]] = None
    owner_id: Optional[str] = None

    class Config:
        populate_by_name = True
        from_attributes = True