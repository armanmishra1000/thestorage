"""
Logging endpoints for DirectDrive backend.
Receives and processes logs from the frontend.
"""
from fastapi import APIRouter, Body, Request
from typing import Dict, Any
import logging
import json
import time

from app.utils.logging_utils import logger, get_memory_usage

router = APIRouter()

@router.post("/logs/event")
async def log_event(request: Request, event_data: Dict[str, Any] = Body(...)):
    """
    Endpoint for general event logging from the frontend.
    
    Args:
        event_data: Event data from the frontend
    """
    log_data = {
        "source": "frontend",
        "timestamp": time.time(),
        "event": event_data,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    logger.info(f"FRONTEND_EVENT: {json.dumps(log_data)}")
    return {"status": "success"}

@router.post("/logs/user_action")
async def log_user_action(request: Request, action_data: Dict[str, Any] = Body(...)):
    """
    Endpoint for user action logging from the frontend.
    
    Args:
        action_data: User action data from the frontend
    """
    log_data = {
        "source": "frontend",
        "timestamp": time.time(),
        "user_action": action_data,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown")
    }
    
    logger.info(f"FRONTEND_USER_ACTION: {json.dumps(log_data)}")
    return {"status": "success"}

@router.post("/logs/file_operation")
async def log_file_operation(request: Request, file_data: Dict[str, Any] = Body(...)):
    """
    Endpoint for file operation logging from the frontend.
    
    Args:
        file_data: File operation data from the frontend
    """
    log_data = {
        "source": "frontend",
        "timestamp": time.time(),
        "file_operation": file_data,
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "server_memory": get_memory_usage()
    }
    
    logger.info(f"FRONTEND_FILE_OPERATION: {json.dumps(log_data)}")
    return {"status": "success"}
