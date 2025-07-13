"""
Download routes for DirectDrive backend.
MVP version with Hetzner Storage-Box only (no Google Drive or Telegram).
"""
import time
import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from urllib.parse import quote
import os

from app.db.mongodb import db
from app.services.hetzner_service import hetzner_client
from app.models.file import FileMetadataInDB
from app.utils.logging_utils import log_file_operation, timed_api_endpoint, log_api_call, get_memory_usage, log_chunk_metrics

router = APIRouter()

@router.get(
    "/files/{file_id}/meta",
    response_model=FileMetadataInDB,
    summary="Get File Metadata",
    tags=["Download"]
)
@timed_api_endpoint
async def get_file_metadata(file_id: str):
    """
    Retrieves the metadata for a specific file, such as its name and size.
    """
    start_time = time.time()
    
    # Log metadata request
    log_file_operation(
        operation_type="metadata_request",
        file_info={"file_id": file_id},
        extra_info={"initial_memory": get_memory_usage()}
    )
    
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        # Log not found error
        log_file_operation(
            operation_type="metadata_error",
            file_info={"file_id": file_id},
            extra_info={
                "error": "File not found",
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        raise HTTPException(status_code=404, detail="File not found")
    
    # Log successful metadata retrieval
    log_file_operation(
        operation_type="metadata_success",
        file_info={
            "file_id": file_id,
            "filename": file_doc.get("filename", ""),
            "size_bytes": file_doc.get("size_bytes", 0),
            "content_type": file_doc.get("content_type", "")
        },
        extra_info={
            "duration_ms": (time.time() - start_time) * 1000,
            "memory": get_memory_usage()
        }
    )
    
    return file_doc

@router.get(
    "/download/stream/{file_id}",
    summary="Stream File for Download",
    tags=["Download"]
)
@timed_api_endpoint
async def stream_download(file_id: str, request: Request):
    """
    Provides a direct download link for a file.
    This endpoint intelligently streams the file from Hetzner Storage-Box.
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Initial memory usage
    initial_memory = get_memory_usage()
    
    # Log download start
    log_file_operation(
        operation_type="download_start",
        file_info={"file_id": file_id, "client_ip": client_ip},
        extra_info={"initial_memory": initial_memory}
    )
    
    file_doc = db.files.find_one({"_id": file_id})
    if not file_doc:
        # Log download error
        log_file_operation(
            operation_type="download_error",
            file_info={"file_id": file_id, "client_ip": client_ip},
            extra_info={
                "error": "File not found",
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        raise HTTPException(status_code=404, detail="File not found")

    filename = file_doc.get("filename", "download")
    filesize = file_doc.get("size_bytes", 0)
    remote_path = file_doc.get("remote_path")
    
    if not remote_path:
        # Log download error
        log_file_operation(
            operation_type="download_error",
            file_info={
                "file_id": file_id,
                "filename": filename,
                "client_ip": client_ip
            },
            extra_info={
                "error": "File remote path not found",
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        raise HTTPException(status_code=404, detail="File remote path not found")

    # Log pre-streaming memory and time
    pre_stream_memory = get_memory_usage()
    pre_stream_time = time.time()
    
    # For local testing, stream from the local storage directory
    async def content_streamer():
        print(f"[STREAMER] Starting stream for '{filename}' from Hetzner.")
        try:
            # For local testing, read from the local storage directory
            local_path = os.path.join(hetzner_client.local_storage_dir, remote_path)
            if not os.path.exists(local_path):
                log_file_operation(
                    operation_type="download_error",
                    file_info={
                        "file_id": file_id,
                        "filename": filename,
                        "remote_path": remote_path,
                        "client_ip": client_ip
                    },
                    extra_info={
                        "error": f"File not found at {local_path}",
                        "duration_ms": (time.time() - pre_stream_time) * 1000
                    }
                )
                raise ValueError(f"File not found at {local_path}")
                
            # Stream the file in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            chunk_count = 0
            total_bytes = 0
            stream_start_time = time.time()
            
            with open(local_path, 'rb') as f:
                while chunk := f.read(chunk_size):
                    chunk_count += 1
                    chunk_size = len(chunk)
                    total_bytes += chunk_size
                    
                    # Log chunk metrics every 10 chunks or for large chunks
                    if chunk_count % 10 == 0 or chunk_size > 5 * 1024 * 1024:
                        log_chunk_metrics(
                            chunk_number=chunk_count,
                            chunk_size=chunk_size,
                            file_id=file_id,
                            remote_path=remote_path
                        )
                    
                    yield chunk
            
            # Calculate streaming duration
            stream_duration = time.time() - stream_start_time
            
            # Log download completion
            log_file_operation(
                operation_type="download_complete",
                file_info={
                    "file_id": file_id,
                    "filename": filename,
                    "size_bytes": filesize,
                    "remote_path": remote_path,
                    "client_ip": client_ip,
                    "chunks_sent": chunk_count,
                    "bytes_sent": total_bytes
                },
                extra_info={
                    "stream_duration_seconds": stream_duration,
                    "transfer_rate_kbps": (total_bytes / 1024) / (stream_duration if stream_duration > 0 else 1),
                    "memory": get_memory_usage()
                }
            )
            
            print(f"[STREAMER] Finished streaming '{filename}' successfully.")
        except Exception as e:
            # Log streaming error
            log_file_operation(
                operation_type="download_error",
                file_info={
                    "file_id": file_id,
                    "filename": filename,
                    "remote_path": remote_path,
                    "client_ip": client_ip
                },
                extra_info={
                    "error": str(e),
                    "duration_ms": (time.time() - pre_stream_time) * 1000,
                    "memory": get_memory_usage()
                }
            )
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
@timed_api_endpoint
async def direct_download(remote_path: str, request: Request):
    """
    Provides a direct download link for a file using its remote path.
    This is used for local testing to simulate the Cloudflare Worker.
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Initial memory usage
    initial_memory = get_memory_usage()
    
    # Log direct download start
    log_file_operation(
        operation_type="direct_download_start",
        file_info={
            "remote_path": remote_path,
            "client_ip": client_ip
        },
        extra_info={
            "initial_memory": initial_memory,
            "download_type": "local_direct"
        }
    )
    try:
        # Find the file in the database by remote_path
        file_doc = db.files.find_one({"remote_path": remote_path})
        if not file_doc:
            # Log direct download error
            log_file_operation(
                operation_type="direct_download_error",
                file_info={
                    "remote_path": remote_path,
                    "client_ip": client_ip
                },
                extra_info={
                    "error": "File not found in database",
                    "duration_ms": (time.time() - start_time) * 1000
                }
            )
            raise HTTPException(status_code=404, detail="File not found in database")
            
        filename = file_doc.get("filename", "download")
        filesize = file_doc.get("size_bytes", 0)
        content_type = file_doc.get("content_type", "application/octet-stream")
        file_id = str(file_doc.get("_id", ""))
        
        # Log file metadata for direct download
        log_file_operation(
            operation_type="direct_download_metadata",
            file_info={
                "file_id": file_id,
                "filename": filename,
                "size_bytes": filesize,
                "content_type": content_type,
                "remote_path": remote_path,
                "client_ip": client_ip
            },
            extra_info={
                "lookup_duration_ms": (time.time() - start_time) * 1000
            }
        )
        
        # Log pre-streaming memory and time
        pre_stream_memory = get_memory_usage()
        pre_stream_time = time.time()
        
        # For local testing, stream from the local storage directory
        async def content_streamer():
            try:
                # For local testing, read from the local storage directory
                local_path = os.path.join(hetzner_client.local_storage_dir, remote_path)
                if not os.path.exists(local_path):
                    # Log file not found error
                    log_file_operation(
                        operation_type="direct_download_error",
                        file_info={
                            "file_id": file_id,
                            "filename": filename,
                            "remote_path": remote_path,
                            "client_ip": client_ip
                        },
                        extra_info={
                            "error": f"File not found at {local_path}",
                            "duration_ms": (time.time() - pre_stream_time) * 1000
                        }
                    )
                    raise ValueError(f"File not found at {local_path}")
                    
                # Stream the file in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                chunk_count = 0
                total_bytes = 0
                stream_start_time = time.time()
                
                with open(local_path, 'rb') as f:
                    while chunk := f.read(chunk_size):
                        chunk_count += 1
                        chunk_size = len(chunk)
                        total_bytes += chunk_size
                        
                        # Log chunk metrics every 10 chunks or for large chunks
                        if chunk_count % 10 == 0 or chunk_size > 5 * 1024 * 1024:
                            log_chunk_metrics(
                                chunk_number=chunk_count,
                                chunk_size=chunk_size,
                                file_id=file_id,
                                remote_path=remote_path
                            )
                        
                        yield chunk
                
                # Calculate streaming duration
                stream_duration = time.time() - stream_start_time
                
                # Log direct download completion
                log_file_operation(
                    operation_type="direct_download_complete",
                    file_info={
                        "file_id": file_id,
                        "filename": filename,
                        "size_bytes": filesize,
                        "remote_path": remote_path,
                        "client_ip": client_ip,
                        "chunks_sent": chunk_count,
                        "bytes_sent": total_bytes
                    },
                    extra_info={
                        "stream_duration_seconds": stream_duration,
                        "transfer_rate_kbps": (total_bytes / 1024) / (stream_duration if stream_duration > 0 else 1),
                        "memory": get_memory_usage(),
                        "memory_change": get_memory_usage() - pre_stream_memory
                    }
                )
                        
            except Exception as e:
                # Log streaming error
                log_file_operation(
                    operation_type="direct_download_error",
                    file_info={
                        "file_id": file_id,
                        "filename": filename,
                        "remote_path": remote_path,
                        "client_ip": client_ip
                    },
                    extra_info={
                        "error": str(e),
                        "duration_ms": (time.time() - pre_stream_time) * 1000,
                        "memory": get_memory_usage()
                    }
                )
                print(f"!!! [STREAMER] An error occurred during direct download for {remote_path}: {e}")
        
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
