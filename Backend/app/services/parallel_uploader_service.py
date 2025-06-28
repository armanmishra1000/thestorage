# server/backend/app/services/parallel_uploader_service.py

import asyncio
import httpx
import os
import random
from pathlib import Path

PARALLEL_CHUNK_SIZE_BYTES = 16 * 1024 * 1024  # 16MB chunks

async def _upload_chunk(client: httpx.AsyncClient, upload_url: str, file_path: Path, start: int, size: int, total_size: int, access_token: str):
    """
    Asynchronously uploads a single chunk with authorization and retries.
    This is a "private" helper function for this module.
    """
    end = start + size - 1
    headers = {
        'Content-Length': str(size),
        'Content-Range': f'bytes {start}-{end}/{total_size}',
        'Authorization': f'Bearer {access_token}'
    }

    with open(file_path, "rb") as f:
        f.seek(start)
        chunk_data = f.read(size)

    max_retries = 5
    for attempt in range(max_retries):
        try:
            print(f"[UPLOADER_SERVICE] Attempt {attempt + 1}/{max_retries} for chunk: bytes {start}-{end}")
            res = await client.put(upload_url, content=chunk_data, headers=headers, timeout=120)
            
            if 500 <= res.status_code < 600:
                res.raise_for_status()

            print(f"[UPLOADER_SERVICE] Chunk {start}-{end} uploaded successfully.")
            return res

        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"!! [UPLOADER_SERVICE] Attempt {attempt + 1} failed for chunk {start}-{end}: {e}")
            if attempt == max_retries - 1:
                print(f"!! [UPLOADER_SERVICE] All retries failed for chunk {start}-{end}. Failing task.")
                raise
            
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            print(f"   -> Waiting for {wait_time:.2f} seconds before retrying...")
            await asyncio.sleep(wait_time)

async def run_parallel_upload(upload_url: str, file_path: Path, access_token: str):
    """
    The main public function of this service.
    Takes an upload_url and performs the parallel upload.
    """
    total_size = os.path.getsize(file_path)
    tasks = []
    
    async with httpx.AsyncClient() as client:
        for start in range(0, total_size, PARALLEL_CHUNK_SIZE_BYTES):
            chunk_size = min(PARALLEL_CHUNK_SIZE_BYTES, total_size - start)
            task = asyncio.create_task(
                _upload_chunk(client, upload_url, file_path, start, chunk_size, total_size, access_token)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for any exceptions that were caught and returned by gather
    for result in results:
        if isinstance(result, Exception):
            raise result  # Re-raise the first exception found
    
    print(f"[UPLOADER_SERVICE] All chunks uploaded successfully via parallel service.")