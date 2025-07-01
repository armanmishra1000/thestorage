# from pydantic import BaseModel, Field
# from typing import List, Optional
# from enum import Enum
# import datetime

# class StorageLocation(str, Enum):
#     GDRIVE = "gdrive"
#     TELEGRAM = "telegram"

# class FileMetadataBase(BaseModel):
#     filename: str
#     size_bytes: int
#     content_type: str

# class FileMetadataCreate(FileMetadataBase):
#     id: str = Field(..., alias="_id")
#     upload_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
#     storage_location: StorageLocation = StorageLocation.GDRIVE
#     gdrive_id: str
#     owner_id: Optional[str] = None # For registered users

# class FileMetadataInDB(FileMetadataBase):
#     id: str = Field(..., alias="_id")
#     upload_date: datetime.datetime
#     storage_location: StorageLocation
#     gdrive_id: Optional[str] = None
#     telegram_message_ids: Optional[List[int]] = None
#     owner_id: Optional[str] = None

#     class Config:
#         populate_by_name = True
#         from_attributes = True

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import datetime

class StorageLocation(str, Enum):
    GDRIVE = "gdrive"
    TELEGRAM = "telegram"
    # New addition for our new flow
    SERVER_DISK = "server_disk" 

# NEW: An enum to track the multi-step upload process
class UploadStatus(str, Enum):
    PENDING = "pending"
    UPLOADING_TO_SERVER = "uploading_to_server"
    UPLOADED_TO_SERVER = "uploaded_to_server"
    UPLOADING_TO_DRIVE = "uploading_to_drive"
    TRANSFERRING_TO_TELEGRAM = "transferring_to_telegram"
    COMPLETED = "completed"
    FAILED = "failed"


class FileMetadataBase(BaseModel):
    filename: str
    size_bytes: int
    content_type: str

class FileMetadataCreate(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    # The final storage location is GDrive, but it has intermediate states
    storage_location: StorageLocation = StorageLocation.SERVER_DISK 
    # NEW: The status field
    status: UploadStatus = UploadStatus.PENDING
    gdrive_id: Optional[str] = None
    telegram_message_ids: Optional[List[int]] = None
    owner_id: Optional[str] = None

class FileMetadataInDB(FileMetadataBase):
    id: str = Field(..., alias="_id")
    upload_date: datetime.datetime
    storage_location: StorageLocation
    # NEW: The status field
    status: UploadStatus
    gdrive_id: Optional[str] = None
    telegram_message_ids: Optional[List[int]] = None
    owner_id: Optional[str] = None

    class Config:
        populate_by_name = True
        from_attributes = True

# NEW: A Pydantic model for the body of our new initiation request
class InitiateUploadRequest(BaseModel):
    filename: str
    size: int
    content_type: str