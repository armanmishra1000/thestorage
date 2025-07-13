"""
Hetzner Storage-Box WebDAV service for file operations.
Production version that uses WebDAV to upload files to Hetzner Storage-Box.
"""
import os
import uuid
import base64
import requests
from typing import AsyncGenerator, BinaryIO, Optional
from urllib.parse import quote

import aiofiles
import aiohttp
from fastapi import UploadFile

from app.core.config import settings


class HetznerWebDAVClient:
    """Client for interacting with Hetzner Storage-Box via WebDAV."""
    
    def __init__(self):
        """Initialize the WebDAV client with credentials from environment variables."""
        self.host = settings.HETZNER_HOST
        self.user = settings.HETZNER_USER
        self.password = settings.HETZNER_PASSWORD
        self.base_path = settings.HETZNER_BASE_PATH
        self.base_url = f"https://{self.host}"
        
        # Check if we're in production mode (on Render)
        self.is_production = os.environ.get('RENDER', '').lower() == 'true'
        
        # For local testing, we'll simulate storage in a local directory
        self.local_storage_dir = "/tmp/directdrive_storage"
        os.makedirs(self.local_storage_dir, exist_ok=True)
        
        if self.is_production:
            print(f"[PRODUCTION MODE] Files will be uploaded to Hetzner Storage-Box at {self.host}{self.base_path}")
        else:
            print(f"[LOCAL TEST MODE] Files will be stored in {self.local_storage_dir}")

    def generate_remote_path(self, filename: str) -> str:
        """
        Generate a unique remote path for a file using UUID.
        
        Args:
            filename: Original filename
            
        Returns:
            A unique path string in the format '{uuid}.{extension}'
        """
        # Extract extension from filename
        _, ext = os.path.splitext(filename)
        
        # Generate UUID for unique filename
        unique_id = str(uuid.uuid4())
        
        # Create path: {uuid}.{extension}
        return f"{unique_id}{ext}"

    def upload_file(self, file_stream: BinaryIO, remote_path: str) -> bool:
        """
        Upload a file to Hetzner Storage-Box or local storage.
        
        Args:
            file_stream: File-like object to upload
            remote_path: Path on the remote server
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.is_production:
                # In production, upload to Hetzner via WebDAV using streaming
                # Create the WebDAV URL
                webdav_url = f"{self.base_url}{self.base_path}/{remote_path}"
                
                # Debug information to help diagnose authentication issues
                print(f"[DEBUG] WebDAV URL: {webdav_url}")
                print(f"[DEBUG] WebDAV Host: {self.host}")
                print(f"[DEBUG] WebDAV User: {self.user}")
                print(f"[DEBUG] WebDAV Password length: {len(self.password) if self.password else 0}")
                print(f"[DEBUG] WebDAV Base Path: {self.base_path}")
                
                # Create basic auth header
                auth = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
                headers = {
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/octet-stream"
                }
                
                # Import requests here to avoid global import
                import requests
                
                # Use a streaming upload approach to avoid loading the entire file into memory
                # This creates a generator that reads the file in chunks
                def file_stream_generator():
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = file_stream.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        
                # Use the streaming generator with requests
                response = requests.put(webdav_url, data=file_stream_generator(), headers=headers)
                
                if response.status_code in (201, 204):
                    print(f"[PRODUCTION MODE] File uploaded to Hetzner: {webdav_url}")
                    return True
                else:
                    print(f"[PRODUCTION MODE] Failed to upload file: {response.status_code} {response.text}")
                    return False
            else:
                # For local testing, save to local directory
                local_path = os.path.join(self.local_storage_dir, remote_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, 'wb') as f:
                    f.write(file_stream.read())
                    
                print(f"[LOCAL TEST MODE] File saved to {local_path}")
                return True
        except Exception as e:
            print(f"Error uploading file: {e}")
            return False

    async def upload_file_async(self, file_stream: BinaryIO, remote_path: str) -> bool:
        """
        Upload a file to Hetzner Storage-Box or local storage asynchronously.
        
        Args:
            file_stream: File-like object to read from (e.g., UploadFile.file)
            remote_path: Path on the remote server
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.is_production:
                # In production, upload to Hetzner via WebDAV
                # Create the WebDAV URL
                webdav_url = f"{self.base_url}{self.base_path}/{remote_path}"
                
                # Create basic auth header
                auth = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
                headers = {
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/octet-stream"
                }
                
                # Debug information to help diagnose authentication issues
                print(f"[DEBUG] WebDAV URL: {webdav_url}")
                print(f"[DEBUG] WebDAV User: {self.user}")
                print(f"[DEBUG] WebDAV Password length: {len(self.password) if self.password else 0}")
                
                # Stream the file to Hetzner in chunks to avoid memory issues
                async with aiohttp.ClientSession() as session:
                    # Create a custom async generator to stream data
                    async def file_stream_generator():
                        chunk_size = 1024 * 1024  # 1MB chunks
                        while True:
                            chunk = file_stream.read(chunk_size)
                            if not chunk:
                                break
                            yield chunk
                    
                    # Use aiohttp's streaming upload capability
                    async with session.put(
                        webdav_url, 
                        data=file_stream_generator(), 
                        headers=headers,
                        chunked=True
                    ) as response:
                        if response.status in (201, 204):
                            print(f"[PRODUCTION MODE] File uploaded to Hetzner: {webdav_url}")
                            return True
                        else:
                            print(f"[PRODUCTION MODE] Failed to upload file: {response.status} {await response.text()}")
                            return False
            else:
                # Create a local file path
                local_path = os.path.join(self.local_storage_dir, remote_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Write chunks directly to the local file
                async with aiofiles.open(local_path, 'wb') as local_file:
                    # Read in chunks to avoid loading entire file into memory
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while chunk := file_stream.read(chunk_size):
                        await local_file.write(chunk)
                        
                print(f"[LOCAL TEST MODE] File saved asynchronously to {local_path}")
                return True
        except Exception as e:
            print(f"Error uploading file asynchronously: {e}")
            return False

    def get_download_url(self, remote_path: str) -> str:
        """
        Get a local URL for downloading a file (simulating Cloudflare Worker URL).
        
        Args:
            remote_path: Path on the remote server
            
        Returns:
            URL for downloading the file
        """
        # For local testing, we'll use a direct file path or a local URL
        # URL encode the remote path for safety
        encoded_path = quote(remote_path)
        
        # In a real production environment, this would be the Cloudflare Worker URL
        # return f"https://dl.mfcnextgen.com/{encoded_path}"
        
        # For local testing, we'll use a local URL
        return f"/api/v1/files/download/{encoded_path}"


# Create a singleton instance
hetzner_client = HetznerWebDAVClient()
