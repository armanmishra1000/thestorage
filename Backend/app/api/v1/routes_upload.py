# # # # # # server/backend/app/api/v1/routes_upload.py (Completely Updated)

# # # # # from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Body
# # # # # from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation
# # # # # from app.models.user import UserInDB
# # # # # from app.services.auth_service import get_current_user, get_current_user_optional
# # # # # from app.db.mongodb import db
# # # # # from app.tasks.file_transfer_task import transfer_gdrive_to_telegram
# # # # # from googleapiclient.errors import HttpError
# # # # # from app.services import google_drive_service
# # # # # import uuid
# # # # # from typing import Optional

# # # # # router = APIRouter()

# # # # # # --- NEW INITIATE ENDPOINT ---
# # # # # @router.post("/upload/initiate")
# # # # # async def initiate_upload(
# # # # #     filename: str = Body(...),
# # # # #     filesize: int = Body(...),
# # # # #     content_type: str = Body(...), # We don't use content_type anymore but can keep it
# # # # #     current_user: Optional[UserInDB] = Depends(get_current_user_optional)
# # # # # ):
# # # # #     # 1. Check file size limits
# # # # #     limit_gb = 15 if current_user else 5
# # # # #     if filesize > limit_gb * 1024 * 1024 * 1024:
# # # # #         raise HTTPException(status_code=413, detail=f"File size exceeds {limit_gb}GB limit.")

# # # # #     # 2. Create the resumable session with improved error handling
# # # # #     try:
# # # # #         # The service no longer needs filesize or content_type for initiation
# # # # #         gdrive_id, upload_url = google_drive_service.create_resumable_upload_session(filename)

# # # # #     # --- ADDED DETAILED EXCEPTION HANDLING ---
# # # # #     except HttpError as e:
# # # # #         # This will catch errors from the Google API client library
# # # # #         print("!!! GOOGLE API HTTP ERROR !!!")
# # # # #         print(f"Error details: {e.content}")
# # # # #         error_content = e.content.decode('utf-8')
# # # # #         raise HTTPException(
# # # # #             status_code=e.resp.status,
# # # # #             detail=f"Google API Error: {error_content}"
# # # # #         )
# # # # #     except Exception as e:
# # # # #         # This will catch other unexpected errors
# # # # #         print(f"!!! UNEXPECTED SERVER ERROR: {e} !!!")
# # # # #         raise HTTPException(
# # # # #             status_code=500,
# # # # #             detail=f"An unexpected error occurred on the server: {str(e)}"
# # # # #         )

# # # # #     # 3. Create initial record in MongoDB
# # # # #     file_id = str(uuid.uuid4())
# # # # #     file_meta = FileMetadataCreate(
# # # # #         _id=file_id,
# # # # #         filename=filename,
# # # # #         size_bytes=filesize,
# # # # #         content_type=content_type,
# # # # #         gdrive_id=gdrive_id,
# # # # #         owner_id=current_user.id if current_user else None
# # # # #     )
# # # # #     db.files.insert_one(file_meta.model_dump(by_alias=True))

# # # # #     return {"file_id": file_id, "upload_url": upload_url}


# # # # # # --- NEW FINALIZE ENDPOINT ---
# # # # # @router.post("/upload/finalize/{file_id}")
# # # # # async def finalize_upload(file_id: str, background_tasks: BackgroundTasks):
# # # # #     file_doc = db.files.find_one({"_id": file_id})
# # # # #     if not file_doc:
# # # # #         raise HTTPException(status_code=404, detail="File ID not found.")

# # # # #     # Here you could add a check against GDrive to confirm the file exists and size matches, for extra security.
    
# # # # #     # Start the background transfer task
# # # # #     background_tasks.add_task(transfer_gdrive_to_telegram, file_id)

# # # # #     return {"message": "Upload finalized. Transfer to permanent storage has begun.", "download_link": f"/download/{file_id}"}


# # # # # # --- These routes remain mostly the same ---
# # # # # @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# # # # # async def get_file_metadata(file_id: str):
# # # # #     file_doc = db.files.find_one({"_id": file_id})
# # # # #     if not file_doc:
# # # # #         raise HTTPException(status_code=404, detail="File not found")
# # # # #     return FileMetadataInDB(**file_doc)

# # # # # @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# # # # # async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
# # # # #     files = db.files.find({"owner_id": current_user.id})
# # # # #     return [FileMetadataInDB(**f) for f in files]

# # # # # @router.get("/download/{file_id}")
# # # # # async def download_file(file_id: str):
# # # # #     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")


# # # # from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, WebSocket, WebSocketDisconnect
# # # # from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation, InitiateUploadRequest, UploadStatus
# # # # from app.models.user import UserInDB
# # # # # from app.services.auth_service import get_optional_current_user # We use the optional one now
# # # # from app.db.mongodb import db
# # # # # We will use this in the next steps, but good to have the import now
# # # # # from app.tasks.file_transfer_task import transfer_gdrive_to_telegram
# # # # from app.services import google_drive_service
# # # # import uuid
# # # # from typing import Optional
# # # # from pathlib import Path # Add this import for path handling
# # # # from app.services.auth_service import try_get_current_user, get_current_user
# # # # from app.services.auth_service import get_current_user_optional
# # # # from fastapi import BackgroundTasks
# # # # from app.tasks.drive_uploader_task import upload_to_drive_task
# # # # import asyncio
# # # # import redis.asyncio as aioredis
# # # # from app.core.config import settings

# # # # router = APIRouter()
# # # # ws_router = APIRouter()

# # # # # Add this list of allowed origins at the top of the file, under your imports
# # # # ALLOWED_ORIGINS = {
# # # #     "http://localhost:4200",
# # # # }

# # # # # Define the directory for temporary uploads
# # # # UPLOAD_DIR = Path("temp_uploads")
# # # # UPLOAD_DIR.mkdir(exist_ok=True) # Ensure the directory exists

# # # # @router.post("/upload/initiate", response_model=dict)
# # # # async def initiate_upload(
# # # #     request: InitiateUploadRequest,
# # # #     current_user: Optional[UserInDB] = Depends(get_current_user_optional) 
# # # # ):
# # # #     """
# # # #     First step of the upload process.
# # # #     The frontend announces its intent to upload a file.
# # # #     The backend generates a unique ID for the session and creates a DB record.
# # # #     """
# # # #     file_id = str(uuid.uuid4())
# # # #     file_meta = FileMetadataCreate(
# # # #         _id=file_id,
# # # #         filename=request.filename,
# # # #         size_bytes=request.size,
# # # #         content_type=request.content_type,
# # # #         owner_id=current_user.id if current_user else None,
# # # #         status=UploadStatus.PENDING
# # # #     )
# # # #     db.files.insert_one(file_meta.model_dump(by_alias=True))
# # # #     return {"file_id": file_id}


# # # # # THIS IS THE NEW WEBSOCKET ENDPOINT
# # # # @ws_router.websocket("/ws/upload/{file_id}")
# # # # async def websocket_upload(
# # # #     websocket: WebSocket, 
# # # #     file_id: str,
# # # #     background_tasks: BackgroundTasks # <-- ADD THIS DEPENDENCY
# # # # ):
# # # #     await websocket.accept()
    
# # # #     file_doc = db.files.find_one({"_id": file_id})
# # # #     if not file_doc:
# # # #         await websocket.close(code=1008)
# # # #         return

# # # #     file_path = UPLOAD_DIR / f"{file_id}.tmp"
# # # #     bytes_written = 0
    
# # # #     db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_SERVER}})

# # # #     try:
# # # #         # We no longer need the 'with open' here, we'll open it inside the loop
# # # #         # to ensure it's closed before the background task starts.
# # # #         f = open(file_path, "wb")
# # # #         while True:
# # # #             # receive_json or receive_bytes? We need to handle both.
# # # #             # We'll use a generic receive() and check the type.
# # # #             message = await websocket.receive()
            
# # # #             if "text" in message:
# # # #                 # This is our signal message
# # # #                 if message["text"] == "DONE":
# # # #                     print(f"Received DONE signal for file_id: {file_id}. Finishing up.")
# # # #                     break # Exit the loop
# # # #             elif "bytes" in message:
# # # #                 # This is a file chunk
# # # #                 f.write(message["bytes"])
# # # #                 bytes_written += len(message["bytes"])
    
# # # #     finally:
# # # #         f.close()
# # # #         print(f"Client connection processing finished for {file_id}.")
        
# # # #         expected_size = file_doc.get("size_bytes", 0)
        
# # # #         if bytes_written == expected_size:
# # # #             db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
# # # #             print(f"File {file_id} successfully saved. Queuing Drive upload task.")
            
# # # #             filename = file_doc.get("filename", "untitled")

# # # #             # --- THIS IS THE KEY CHANGE ---
# # # #             # Send the task to the Celery queue instead of using BackgroundTasks
# # # #             # We must convert the Path object to a string, as Celery messages must be serializable.
# # # #             upload_to_drive_task.delay(file_id, str(file_path), filename)
# # # #             # --- END OF CHANGE ---
            
# # # #         else:
# # # #             db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # # #             print(f"File {file_id} upload failed. Expected {expected_size}, got {bytes_written}.")
# # # #             if file_path.exists():
# # # #                 file_path.unlink() # Delete partial file
        
# # # #         # The server now proactively closes the connection
# # # #         await websocket.close()


# # # # # We are keeping the old routes for now, but they will be replaced.
# # # # @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# # # # async def get_file_metadata(file_id: str):
# # # #     file_doc = db.files.find_one({"_id": file_id})
# # # #     if not file_doc:
# # # #         raise HTTPException(status_code=404, detail="File not found")
# # # #     return FileMetadataInDB(**file_doc)

# # # # @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# # # # async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
# # # #     files = db.files.find({"owner_id": current_user.id})
# # # #     return [FileMetadataInDB(**f) for f in files]

# # # # @router.get("/download/{file_id}")
# # # # async def download_file(file_id: str):
# # # #     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")


# # # # @ws_router.websocket("/ws/progress/{file_id}")
# # # # async def websocket_progress(websocket: WebSocket, file_id: str):
# # # #     """
# # # #     Acts as a bridge between Redis Pub/Sub and the frontend WebSocket.
# # # #     """
# # # #     await websocket.accept()
    
# # # #     # Create a new async redis connection
# # # #     redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
# # # #     pubsub = redis_conn.pubsub()
# # # #     channel_name = f"progress_{file_id}"
# # # #     await pubsub.subscribe(channel_name)
    
# # # #     print(f"[PROGRESS_WS] Client connected and subscribed to {channel_name}")
    
# # # #     try:
# # # #         while True:
# # # #             # Listen for messages from Redis
# # # #             message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
# # # #             if message:
# # # #                 data = message['data']
# # # #                 # Forward the message to the frontend client
# # # #                 await websocket.send_text(data)
# # # #                 print(f"[PROGRESS_WS] Forwarded message to client: {data}")
                
# # # #                 # If the message is a success or error, we're done.
# # # #                 import json
# # # #                 if json.loads(data)['type'] in ['success', 'error']:
# # # #                     break # Exit the loop
            
# # # #             # This small sleep prevents the loop from consuming 100% CPU if Redis is slow
# # # #             await asyncio.sleep(0.01)

# # # #     except WebSocketDisconnect:
# # # #         print(f"[PROGRESS_WS] Client for {file_id} disconnected.")
# # # #     finally:
# # # #         # Clean up the subscription and connection
# # # #         await pubsub.unsubscribe(channel_name)
# # # #         await redis_conn.close()
# # # #         print(f"[PROGRESS_WS] Unsubscribed and closed connection for {file_id}.")




# # # from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
# # # from app.models.file import FileMetadataCreate, FileMetadataInDB, StorageLocation, InitiateUploadRequest, UploadStatus
# # # from app.models.user import UserInDB
# # # from app.db.mongodb import db
# # # from app.services import google_drive_service
# # # import uuid
# # # from typing import Optional
# # # from pathlib import Path
# # # from app.services.auth_service import get_current_user_optional, get_current_user
# # # from app.tasks.drive_uploader_task import upload_to_drive_task
# # # import asyncio
# # # import redis.asyncio as aioredis
# # # from app.core.config import settings
# # # import json

# # # router = APIRouter()
# # # ws_router = APIRouter()

# # # # Define the directory for temporary uploads
# # # UPLOAD_DIR = Path("temp_uploads")
# # # UPLOAD_DIR.mkdir(exist_ok=True) # Ensure the directory exists

# # # @router.post("/upload/initiate", response_model=dict)
# # # async def initiate_upload(
# # #     request: InitiateUploadRequest,
# # #     current_user: Optional[UserInDB] = Depends(get_current_user_optional) 
# # # ):
# # #     """
# # #     First step of the upload process.
# # #     The frontend announces its intent to upload a file.
# # #     The backend generates a unique ID for the session and creates a DB record.
# # #     """
# # #     file_id = str(uuid.uuid4())
# # #     file_meta = FileMetadataCreate(
# # #         _id=file_id,
# # #         filename=request.filename,
# # #         size_bytes=request.size,
# # #         content_type=request.content_type,
# # #         owner_id=current_user.id if current_user else None,
# # #         status=UploadStatus.PENDING
# # #     )
# # #     db.files.insert_one(file_meta.model_dump(by_alias=True))
# # #     return {"file_id": file_id}


# # # # --- NEW COMBINED WEBSOCKET ENDPOINT ---
# # # # This single endpoint handles both receiving the file from the browser
# # # # and streaming the Google Drive upload progress back to the browser.
# # # @ws_router.websocket("/ws/upload/{file_id}")
# # # async def websocket_upload_and_progress(websocket: WebSocket, file_id: str):
# # #     await websocket.accept()

# # #     # === PHASE 1: RECEIVE FILE FROM BROWSER ===
# # #     # During this phase, the frontend should show a generic "Uploading..." message.
    
# # #     file_doc = db.files.find_one({"_id": file_id})
# # #     if not file_doc:
# # #         await websocket.send_json({"type": "error", "value": "File ID not found."})
# # #         await websocket.close(code=1008)
# # #         return

# # #     file_path = UPLOAD_DIR / f"{file_id}.tmp"
# # #     bytes_written = 0
# # #     db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_SERVER}})

# # #     try:
# # #         with open(file_path, "wb") as f:
# # #             while True:
# # #                 message = await websocket.receive()
# # #                 if "text" in message and message["text"] == "DONE":
# # #                     print(f"Received DONE signal for {file_id}. Finishing server upload.")
# # #                     break
# # #                 elif "bytes" in message:
# # #                     f.write(message["bytes"])
# # #                     bytes_written += len(message["bytes"])
# # #     except WebSocketDisconnect:
# # #         # Clean up if client disconnects mid-upload
# # #         if file_path.exists():
# # #             file_path.unlink()
# # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # #         print(f"Client disconnected during file upload for {file_id}. Temp file deleted.")
# # #         return # Exit the function

# # #     # --- File reception is complete, now verify and start backend task ---
# # #     print(f"File reception complete for {file_id}. Verifying size...")
# # #     expected_size = file_doc.get("size_bytes", 0)

# # #     if bytes_written != expected_size:
# # #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# # #         if file_path.exists():
# # #             file_path.unlink()
# # #         error_msg = f"File upload failed verification. Expected {expected_size}, received {bytes_written}."
# # #         print(error_msg)
# # #         await websocket.send_json({"type": "error", "value": error_msg})
# # #         await websocket.close()
# # #         return

# # #     # --- Start the Celery task for the Google Drive upload ---
# # #     db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
# # #     filename = file_doc.get("filename", "untitled")
# # #     upload_to_drive_task.delay(file_id, str(file_path), filename)
# # #     print(f"File {file_id} saved. Queued Drive upload task. Switching to progress tracking.")

# # #     # === PHASE 2: STREAM PROGRESS TO BROWSER ===
# # #     # The connection is still open. Now we send progress updates for the GDrive upload.
# # #     # The frontend can now display the real-time progress bar.
# # #     redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
# # #     pubsub = redis_conn.pubsub()
# # #     channel_name = f"progress_{file_id}"
# # #     await pubsub.subscribe(channel_name)
    
# # #     try:
# # #         while True:
# # #             message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
# # #             if message:
# # #                 data = message['data']
# # #                 await websocket.send_text(data)
# # #                 print(f"[PROGRESS_WS] Forwarded to {file_id}: {data}")
# # #                 if json.loads(data)['type'] in ['success', 'error']:
# # #                     break # We are done, break the loop
# # #     except WebSocketDisconnect:
# # #         print(f"[PROGRESS_WS] Client for {file_id} disconnected during progress tracking.")
# # #     finally:
# # #         # Clean up Redis resources and close the connection
# # #         await pubsub.unsubscribe(channel_name)
# # #         await redis_conn.close()
# # #         print(f"[PROGRESS_WS] Unsubscribed and closed Redis connection for {file_id}.")


# # # # These HTTP routes remain the same
# # # @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# # # async def get_file_metadata(file_id: str):
# # #     file_doc = db.files.find_one({"_id": file_id})
# # #     if not file_doc:
# # #         raise HTTPException(status_code=404, detail="File not found")
# # #     return FileMetadataInDB(**file_doc)

# # # @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# # # async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
# # #     files = db.files.find({"owner_id": current_user.id})
# # #     return [FileMetadataInDB(**f) for f in files]

# # # @router.get("/download/{file_id}")
# # # async def download_file(file_id: str):
# # #     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")


# # from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
# # from app.models.file import FileMetadataCreate, FileMetadataInDB, InitiateUploadRequest, UploadStatus
# # from app.models.user import UserInDB
# # from app.db.mongodb import db
# # import uuid
# # from typing import Optional
# # from pathlib import Path
# # from app.services.auth_service import get_current_user_optional, get_current_user
# # from app.tasks.drive_uploader_task import upload_to_drive_task
# # import asyncio
# # import redis.asyncio as aioredis
# # from app.core.config import settings
# # import json

# # router = APIRouter()
# # ws_router = APIRouter()

# # UPLOAD_DIR = Path("temp_uploads")
# # UPLOAD_DIR.mkdir(exist_ok=True)

# # @router.post("/upload/initiate", response_model=dict)
# # async def initiate_upload(
# #     request: InitiateUploadRequest,
# #     current_user: Optional[UserInDB] = Depends(get_current_user_optional)
# # ):
# #     """
# #     First step of the upload process.
# #     The frontend announces its intent to upload a file.
# #     The backend generates a unique ID for the session and creates a DB record.
# #     """
# #     file_id = str(uuid.uuid4())
# #     file_meta = FileMetadataCreate(
# #         _id=file_id,
# #         filename=request.filename,
# #         size_bytes=request.size,
# #         content_type=request.content_type,
# #         owner_id=current_user.id if current_user else None,
# #         status=UploadStatus.PENDING
# #     )
# #     db.files.insert_one(file_meta.model_dump(by_alias=True))
# #     return {"file_id": file_id}


# # # --- THE DEFINITIVE, REFINED WEBSOCKET ENDPOINT ---
# # @ws_router.websocket("/ws/upload/{file_id}")
# # async def websocket_upload_and_progress(websocket: WebSocket, file_id: str):
# #     """
# #     Handles the entire upload process over a single WebSocket connection.
# #     - Phase 1: Receives the file from the browser to the server's temp storage.
# #                The frontend should show a generic loading spinner during this phase.
# #     - Phase 2: Streams the server-to-Google-Drive upload progress back to the browser.
# #                The frontend shows the real-time progress bar during this phase.
# #     """
# #     await websocket.accept()
    
# #     file_doc = db.files.find_one({"_id": file_id})
# #     if not file_doc:
# #         await websocket.send_json({"type": "error", "value": "File ID not found."})
# #         await websocket.close(code=1008)
# #         return

# #     file_path = UPLOAD_DIR / f"{file_id}.tmp"
    
# #     # === PHASE 1: RECEIVE FILE FROM BROWSER (User sees a spinner) ===
# #     try:
# #         bytes_written = 0
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADING_TO_SERVER}})
        
# #         with open(file_path, "wb") as f:
# #             while True:
# #                 message = await websocket.receive()
# #                 if "text" in message and message["text"] == "DONE":
# #                     print(f"[{file_id}] Browser-to-server upload complete.")
# #                     break
# #                 elif "bytes" in message:
# #                     f.write(message["bytes"])
# #                     bytes_written += len(message["bytes"])

# #         # --- Verification Step ---
# #         expected_size = file_doc.get("size_bytes", 0)
# #         if bytes_written != expected_size:
# #             raise ValueError(f"File size mismatch. Expected {expected_size}, got {bytes_written}.")

# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
        
# #         # === TRANSITION: SIGNAL TO FRONTEND TO SHOW PROGRESS BAR ===
# #         # This message tells the frontend to switch from a spinner to the progress bar.
# #         await websocket.send_json({
# #             "type": "processing_started", 
# #             "value": "Uploading to Google Drive..."
# #         })
        
# #         # --- Start the background task ---
# #         filename = file_doc.get("filename", "untitled")
# #         upload_to_drive_task.delay(file_id, str(file_path), filename)
# #         print(f"[{file_id}] Celery task for GDrive upload has been dispatched.")

# #     except (WebSocketDisconnect, ValueError) as e:
# #         if file_path.exists():
# #             file_path.unlink()
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# #         error_message = f"Upload failed during browser-to-server transfer: {e}"
# #         print(f"[{file_id}] {error_message}")
# #         try:
# #             # Try to inform the client before closing
# #             await websocket.send_json({"type": "error", "value": error_message})
# #         except RuntimeError: pass # Connection may already be closed
# #         return

# #     # === PHASE 2: STREAM GDRIVE PROGRESS TO BROWSER (User sees progress bar) ===
# #     redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
# #     pubsub = redis_conn.pubsub()
# #     channel_name = f"progress_{file_id}"
# #     await pubsub.subscribe(channel_name)
    
# #     print(f"[{file_id}] Now listening on Redis channel '{channel_name}' for GDrive progress.")
    
# #     try:
# #         while True:
# #             # Listen for a message from Redis, with a long timeout to handle long uploads
# #             message = await asyncio.wait_for(
# #                 pubsub.get_message(ignore_subscribe_messages=True, timeout=None),
# #                 timeout=600 # 10-minute timeout for any single progress update
# #             )
# #             if message:
# #                 data = message['data']
# #                 await websocket.send_text(data) # Forward progress to the client
                
# #                 # If the task is finished (success/error), we can stop listening.
# #                 if json.loads(data)['type'] in ['success', 'error']:
# #                     break
# #     except (WebSocketDisconnect, asyncio.TimeoutError) as e:
# #         print(f"[{file_id}] Client disconnected or progress timed out: {e}")
# #     finally:
# #         await pubsub.unsubscribe(channel_name)
# #         await redis_conn.close()
# #         await websocket.close()
# #         print(f"[{file_id}] Cleaned up resources and closed WebSocket.")


# # # --- Other HTTP routes remain unchanged ---
# # @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# # async def get_file_metadata(file_id: str):
# #     file_doc = db.files.find_one({"_id": file_id})
# #     if not file_doc:
# #         raise HTTPException(status_code=404, detail="File not found")
# #     return FileMetadataInDB(**file_doc)

# # @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# # async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
# #     files = db.files.find({"owner_id": current_user.id})
# #     return [FileMetadataInDB(**f) for f in files]

# # @router.get("/download/{file_id}")
# # async def download_file(file_id: str):
# #     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")



# # from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
# # from app.models.file import FileMetadataCreate, FileMetadataInDB, InitiateUploadRequest, UploadStatus
# # from app.models.user import UserInDB
# # from app.db.mongodb import db
# # import uuid
# # from typing import Optional
# # from pathlib import Path
# # from app.services.auth_service import get_current_user_optional, get_current_user
# # from app.tasks.drive_uploader_task import upload_to_drive_task
# # import asyncio
# # import redis.asyncio as aioredis
# # from app.core.config import settings
# # import json

# # router = APIRouter()
# # ws_router = APIRouter()

# # UPLOAD_DIR = Path("temp_uploads")
# # UPLOAD_DIR.mkdir(exist_ok=True)

# # @router.post("/upload/initiate", response_model=dict)
# # async def initiate_upload(
# #     request: InitiateUploadRequest,
# #     current_user: Optional[UserInDB] = Depends(get_current_user_optional)
# # ):
# #     """
# #     First step: The frontend announces its intent to upload a file.
# #     """
# #     file_id = str(uuid.uuid4())
# #     file_meta = FileMetadataCreate(
# #         _id=file_id,
# #         filename=request.filename,
# #         size_bytes=request.size,
# #         content_type=request.content_type,
# #         owner_id=current_user.id if current_user else None,
# #         status=UploadStatus.PENDING
# #     )
# #     db.files.insert_one(file_meta.model_dump(by_alias=True))
# #     return {"file_id": file_id}


# # # --- THE ONLY WEBSOCKET ENDPOINT ---
# # @ws_router.websocket("/ws/upload/{file_id}")
# # async def websocket_upload_and_progress(websocket: WebSocket, file_id: str):
# #     """
# #     Handles the entire upload process over a single, persistent WebSocket connection.
# #     """
# #     await websocket.accept()
    
# #     file_doc = db.files.find_one({"_id": file_id})
# #     if not file_doc:
# #         await websocket.close(code=1008, reason="File ID not found")
# #         return

# #     file_path = UPLOAD_DIR / f"{file_id}.tmp"
    
# #     # === PHASE 1: RECEIVE FILE FROM BROWSER ===
# #     try:
# #         with open(file_path, "wb") as f:
# #             while True:
# #                 message = await websocket.receive()
# #                 if "text" in message and message["text"] == "DONE":
# #                     print(f"[{file_id}] Browser-to-server upload complete.")
# #                     break
# #                 elif "bytes" in message:
# #                     f.write(message["bytes"])
        
# #         filename = file_doc.get("filename", "untitled")
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
        
# #         await websocket.send_json({"type": "processing_started", "value": "Uploading to Google Drive..."})
        
# #         upload_to_drive_task.delay(file_id, str(file_path), filename)
# #         print(f"[{file_id}] Dispatched Celery task for GDrive upload.")

# #     except WebSocketDisconnect:
# #         print(f"[{file_id}] Client disconnected during browser-to-server upload. Cleaning up.")
# #         if file_path.exists():
# #             file_path.unlink()
# #         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
# #         return

# #     # === PHASE 2: STREAM GDRIVE PROGRESS TO BROWSER ===
# #     redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
# #     pubsub = redis_conn.pubsub()
# #     channel_name = f"progress_{file_id}"
# #     await pubsub.subscribe(channel_name)
    
# #     print(f"[{file_id}] Listening on Redis for GDrive progress...")
    
# #     try:
# #         # --- THIS IS THE FIX ---
# #         # Use the robust 'async for' pattern to listen for messages.
# #         # This will block and wait indefinitely for new messages.
# #         async for message in pubsub.listen():
# #             # We only care about actual data messages, not subscribe confirmations
# #             if message and message["type"] == "message":
# #                 data = message['data']
# #                 await websocket.send_text(data) # Forward progress to the client
# #                 # If the task is finished (success/error), we can stop listening.
# #                 if json.loads(data)['type'] in ['success', 'error']:
# #                     break 
# #     except WebSocketDisconnect:
# #         print(f"[{file_id}] Client disconnected during progress monitoring.")
# #     finally:
# #         # Gracefully clean up all resources
# #         await pubsub.unsubscribe(channel_name)
# #         await redis_conn.close()
# #         try:
# #             await websocket.close()
# #         except RuntimeError:
# #             pass # Ignore if already closed
# #         print(f"[{file_id}] Cleaned up resources and closed connection.")


# # # --- HTTP routes are unchanged ---
# # @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# # async def get_file_metadata(file_id: str):
# #     file_doc = db.files.find_one({"_id": file_id})
# #     if not file_doc:
# #         raise HTTPException(status_code=404, detail="File not found")
# #     return FileMetadataInDB(**file_doc)

# # @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# # async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
# #     files = db.files.find({"owner_id": current_user.id})
# #     return [FileMetadataInDB(**f) for f in files]

# # @router.get("/download/{file_id}")
# # async def download_file(file_id: str):
# #     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")





# from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
# from app.models.file import FileMetadataCreate, FileMetadataInDB, InitiateUploadRequest, UploadStatus
# from app.models.user import UserInDB
# from app.db.mongodb import db
# import uuid
# from typing import Optional
# from pathlib import Path
# from app.services.auth_service import get_current_user_optional, get_current_user
# from app.tasks.drive_uploader_task import upload_to_drive_task
# import asyncio
# import redis.asyncio as aioredis
# from app.core.config import settings
# import json

# router = APIRouter()
# ws_router = APIRouter()

# UPLOAD_DIR = Path("temp_uploads")
# UPLOAD_DIR.mkdir(exist_ok=True)

# @router.post("/upload/initiate", response_model=dict)
# async def initiate_upload(
#     request: InitiateUploadRequest,
#     current_user: Optional[UserInDB] = Depends(get_current_user_optional)
# ):
#     """
#     First step: The frontend announces its intent to upload a file.
#     """
#     file_id = str(uuid.uuid4())
#     file_meta = FileMetadataCreate(
#         _id=file_id,
#         filename=request.filename,
#         size_bytes=request.size,
#         content_type=request.content_type,
#         owner_id=current_user.id if current_user else None,
#         status=UploadStatus.PENDING
#     )
#     db.files.insert_one(file_meta.model_dump(by_alias=True))
#     return {"file_id": file_id}


# # --- THE DEFINITIVE, ROBUST WEBSOCKET ENDPOINT ---
# @ws_router.websocket("/ws/upload/{file_id}")
# async def websocket_upload_and_progress(websocket: WebSocket, file_id: str):
#     """
#     Handles the entire upload process using a robust producer-consumer pattern
#     to ensure the WebSocket connection stays alive.
#     """
#     await websocket.accept()
    
#     file_doc = db.files.find_one({"_id": file_id})
#     if not file_doc:
#         await websocket.close(code=1008, reason="File ID not found")
#         return

#     file_path = UPLOAD_DIR / f"{file_id}.tmp"
    
#     # === PHASE 1: RECEIVE FILE FROM BROWSER ===
#     try:
#         with open(file_path, "wb") as f:
#             while True:
#                 message = await websocket.receive()
#                 if "text" in message and message["text"] == "DONE":
#                     print(f"[{file_id}] Browser-to-server upload complete.")
#                     break
#                 elif "bytes" in message:
#                     f.write(message["bytes"])
        
#         filename = file_doc.get("filename", "untitled")
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
        
#         await websocket.send_json({"type": "processing_started", "value": "Uploading to Google Drive..."})
        
#         upload_to_drive_task.delay(file_id, str(file_path), filename)
#         print(f"[{file_id}] Dispatched Celery task for GDrive upload.")

#     except WebSocketDisconnect:
#         print(f"[{file_id}] Client disconnected during file reception. Cleaning up.")
#         if file_path.exists():
#             file_path.unlink()
#         db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
#         return

#     # === PHASE 2: STREAM GDRIVE PROGRESS USING A QUEUE ===
#     # This pattern robustly keeps the connection alive.
#     queue = asyncio.Queue()
    
#     async def redis_listener(q: asyncio.Queue):
#         """Producer: Listens to Redis and puts messages on the queue."""
#         redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
#         pubsub = redis_conn.pubsub()
#         await pubsub.subscribe(f"progress_{file_id}")
#         print(f"[{file_id}] Redis listener subscribed.")
#         try:
#             async for message in pubsub.listen():
#                 if message and message["type"] == "message":
#                     await q.put(message['data'])
#                     if json.loads(message['data'])['type'] in ['success', 'error']:
#                         break
#         finally:
#             await pubsub.unsubscribe()
#             await redis_conn.close()
#             await q.put(None) # Sentinel value to stop the consumer
#             print(f"[{file_id}] Redis listener cleaned up.")

#     async def websocket_sender(q: asyncio.Queue):
#         """Consumer: Gets messages from the queue and sends them to the WebSocket."""
#         print(f"[{file_id}] WebSocket sender started.")
#         while True:
#             data = await q.get()
#             if data is None: # Sentinel value received
#                 break
#             await websocket.send_text(data)
#         print(f"[{file_id}] WebSocket sender finished.")

#     # Create and run the two tasks concurrently.
#     listener_task = asyncio.create_task(redis_listener(queue))
#     sender_task = asyncio.create_task(websocket_sender(queue))

#     # Wait for both tasks to complete. This is what keeps the main function alive.
#     await asyncio.gather(listener_task, sender_task)
    
#     # Final cleanup
#     try:
#         await websocket.close()
#     except RuntimeError:
#         pass # Ignore if already closed by sender/client
#     print(f"[{file_id}] All tasks finished. Connection closed.")


# # --- HTTP routes remain unchanged ---
# @router.get("/files/{file_id}", response_model=FileMetadataInDB)
# async def get_file_metadata(file_id: str):
#     file_doc = db.files.find_one({"_id": file_id})
#     if not file__doc:
#         raise HTTPException(status_code=404, detail="File not found")
#     return FileMetadataInDB(**file_doc)

# @router.get("/files/me/history", response_model=list[FileMetadataInDB])
# async def get_user_file_history(current_user: UserInDB = Depends(get_current_user)):
#     files = db.files.find({"owner_id": current_user.id})
#     return [FileMetadataInDB(**f) for f in files]

# @router.get("/download/{file_id}")
# async def download_file(file_id: str):
#     raise HTTPException(status_code=501, detail="Download functionality not fully implemented.")



from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from app.models.file import FileMetadataCreate, FileMetadataInDB, InitiateUploadRequest, UploadStatus
from app.models.user import UserInDB
from app.db.mongodb import db
import uuid
from typing import Optional
from pathlib import Path
from app.services.auth_service import get_current_user_optional, get_current_user
from app.tasks.drive_uploader_task import upload_to_drive_task
import asyncio
import redis.asyncio as aioredis
from app.core.config import settings
import json

router = APIRouter()
ws_router = APIRouter()

UPLOAD_DIR = Path("temp_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload/initiate", response_model=dict)
async def initiate_upload(
    request: InitiateUploadRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user_optional)
):
    """
    First step: The frontend announces its intent to upload a file.
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


# --- THE DEFINITIVE, ROBUST WEBSOCKET ENDPOINT ---
@ws_router.websocket("/ws/upload/{file_id}")
async def websocket_upload_and_progress(websocket: WebSocket, file_id: str):
    """
    Handles the entire upload process using a robust producer-consumer pattern
    to ensure the WebSocket connection stays alive.
    """
    await websocket.accept()
    
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        await websocket.close(code=1008, reason="File ID not found")
        return

    file_path = UPLOAD_DIR / f"{file_id}.tmp"
    
    # === PHASE 1: RECEIVE FILE FROM BROWSER ===
    try:
        with open(file_path, "wb") as f:
            while True:
                message = await websocket.receive()
                if "text" in message and message["text"] == "DONE":
                    print(f"[{file_id}] Browser-to-server upload complete.")
                    break
                elif "bytes" in message:
                    f.write(message["bytes"])
        
        filename = file_doc.get("filename", "untitled")
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.UPLOADED_TO_SERVER}})
        
        await websocket.send_json({"type": "processing_started", "value": "Uploading to Google Drive..."})
        
        upload_to_drive_task.delay(file_id, str(file_path), filename)
        print(f"[{file_id}] Dispatched Celery task for GDrive upload.")

    except WebSocketDisconnect:
        print(f"[{file_id}] Client disconnected during file reception. Cleaning up.")
        if file_path.exists():
            file_path.unlink()
        db.files.update_one({"_id": file_id}, {"$set": {"status": UploadStatus.FAILED}})
        return

    # === PHASE 2: STREAM GDRIVE PROGRESS USING A QUEUE ===
    # This pattern robustly keeps the connection alive.
    queue = asyncio.Queue()
    
    async def redis_listener(q: asyncio.Queue):
        """Producer: Listens to Redis and puts messages on the queue."""
        redis_conn = aioredis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)
        pubsub = redis_conn.pubsub()
        await pubsub.subscribe(f"progress_{file_id}")
        print(f"[{file_id}] Redis listener subscribed.")
        try:
            async for message in pubsub.listen():
                if message and message["type"] == "message":
                    await q.put(message['data'])
                    if json.loads(message['data'])['type'] in ['success', 'error']:
                        break
        finally:
            await pubsub.unsubscribe()
            await redis_conn.close()
            await q.put(None) # Sentinel value to stop the consumer
            print(f"[{file_id}] Redis listener cleaned up.")

    async def websocket_sender(q: asyncio.Queue):
        """Consumer: Gets messages from the queue and sends them to the WebSocket."""
        print(f"[{file_id}] WebSocket sender started.")
        while True:
            data = await q.get()
            if data is None: # Sentinel value received
                break
            await websocket.send_text(data)
        print(f"[{file_id}] WebSocket sender finished.")

    # Create and run the two tasks concurrently.
    listener_task = asyncio.create_task(redis_listener(queue))
    sender_task = asyncio.create_task(websocket_sender(queue))

    # Wait for both tasks to complete. This is what keeps the main function alive.
    await asyncio.gather(listener_task, sender_task)
    
    # Final cleanup
    try:
        await websocket.close()
    except RuntimeError:
        pass # Ignore if already closed by sender/client
    print(f"[{file_id}] All tasks finished. Connection closed.")


# --- HTTP routes are unchanged ---
@router.get("/files/{file_id}", response_model=FileMetadataInDB)
async def get_file_metadata(file_id: str):
    file_doc = db.files.find_one({"_id": file_id})
    # --- THIS IS THE FIX ---
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