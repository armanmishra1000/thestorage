"""
Logging utilities for DirectDrive backend.
Provides structured logging for file operations, performance metrics, and system health.
"""
import time
import os
import psutil
import logging
import json
from functools import wraps
from typing import Callable, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create logger
logger = logging.getLogger('directdrive')

def get_memory_usage() -> Dict[str, float]:
    """Get current memory usage of the process."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    return {
        "rss_mb": memory_info.rss / (1024 * 1024),  # Resident Set Size in MB
        "vms_mb": memory_info.vms / (1024 * 1024),  # Virtual Memory Size in MB
        "percent": process.memory_percent()
    }

def log_file_operation(operation_type: str, file_info: Dict[str, Any], extra_info: Optional[Dict[str, Any]] = None):
    """
    Log file operations with detailed metrics.
    
    Args:
        operation_type: Type of operation (upload_start, upload_complete, download, etc.)
        file_info: Information about the file (id, name, size, etc.)
        extra_info: Additional information to include in the log
    """
    log_data = {
        "operation": operation_type,
        "file": file_info,
        "timestamp": time.time(),
        "memory": get_memory_usage()
    }
    
    if extra_info:
        log_data.update(extra_info)
    
    logger.info(f"FILE_OPERATION: {json.dumps(log_data)}")

def log_api_call(endpoint: str, method: str, status_code: int, duration_ms: float, extra_info: Optional[Dict[str, Any]] = None):
    """
    Log API calls with performance metrics.
    
    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        status_code: HTTP status code
        duration_ms: Duration of the API call in milliseconds
        extra_info: Additional information to include in the log
    """
    log_data = {
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
        "memory": get_memory_usage()
    }
    
    if extra_info:
        log_data.update(extra_info)
    
    logger.info(f"API_CALL: {json.dumps(log_data)}")

def timed_api_endpoint(func: Callable):
    """
    Decorator to time API endpoints and log performance metrics.
    
    Args:
        func: The API endpoint function to time
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Extract request information from FastAPI
            request = None
            for arg in args:
                if hasattr(arg, "method") and hasattr(arg, "url"):
                    request = arg
                    break
            
            if request:
                log_api_call(
                    endpoint=str(request.url.path),
                    method=request.method,
                    status_code=200,  # Assuming success if no exception
                    duration_ms=duration_ms
                )
            
            return result
            
        except Exception as e:
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Log the error with the API call
            log_api_call(
                endpoint="unknown",  # We might not have access to the request here
                method="unknown",
                status_code=500,  # Assuming server error
                duration_ms=duration_ms,
                extra_info={"error": str(e)}
            )
            
            # Re-raise the exception
            raise
    
    return wrapper

def log_chunk_metrics(chunk_number: int, chunk_size: int, total_chunks: Optional[int] = None, 
                     file_id: str = "", remote_path: str = ""):
    """
    Log metrics for individual chunks during streaming operations.
    
    Args:
        chunk_number: Current chunk number
        chunk_size: Size of the current chunk in bytes
        total_chunks: Total number of chunks (if known)
        file_id: ID of the file being processed
        remote_path: Remote path of the file
    """
    log_data = {
        "operation": "chunk_processed",
        "chunk_number": chunk_number,
        "chunk_size_bytes": chunk_size,
        "file_id": file_id,
        "remote_path": remote_path,
        "memory": get_memory_usage(),
        "timestamp": time.time()
    }
    
    if total_chunks is not None:
        log_data["total_chunks"] = total_chunks
        log_data["progress_percent"] = (chunk_number / total_chunks) * 100
    
    logger.debug(f"CHUNK_METRICS: {json.dumps(log_data)}")
