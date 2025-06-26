import httpx
from app.core.config import settings
from typing import List

TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
CHUNK_SIZE_MB = 15
CHUNK_SIZE_BYTES = CHUNK_SIZE_MB * 1024 * 1024

async def upload_chunk_to_telegram(chunk: bytes, filename: str) -> int:
    async with httpx.AsyncClient(timeout=60.0) as client:
        url = f"{TELEGRAM_API_URL}/sendDocument"
        params = {'chat_id': settings.TELEGRAM_CHANNEL_ID}
        files = {'document': (filename, chunk, 'application/octet-stream')}
        
        response = await client.post(url, params=params, files=files)
        response.raise_for_status()
        data = response.json()
        if data['ok']:
            return data['result']['message_id']
        else:
            raise Exception(f"Telegram API Error: {data['description']}")

async def download_chunk_from_telegram(message_id: int) -> bytes:
     async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Get file_id from message_id
        get_msg_url = f"{TELEGRAM_API_URL}/forwardMessage"
        # A trick to get file_id: forward the message to the bot itself and capture the response
        # A better way is to store the file_id in the DB in the first place.
        # Let's simplify and get the file path directly.
        
        # 1. Get file_path
        get_file_path_url = f"{TELEGRAM_API_URL}/getFile"
        params = {'file_id': await get_file_id_from_message(message_id)}
        response = await client.get(get_file_path_url, params=params)
        response.raise_for_status()
        file_path = response.json()['result']['file_path']

        # 2. Download the file content
        file_download_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
        response = await client.get(file_download_url)
        response.raise_for_status()
        return response.content

async def get_file_id_from_message(message_id: int) -> str:
    # This is a bit of a hack. The best way is to store the file_id
    # when you upload, but the API doesn't return it on sendDocument.
    # We can get it by editing the message caption.
    # For now, we will assume a simpler model where the bot can retrieve it.
    # The Telegram API for bots is complex for direct downloads.
    # A more robust solution might involve a user account (Telethon/Pyrogram)
    # but let's stick to the Bot API.
    # The simplest way is to use a library that handles this.
    # Let's mock this for now, as it's the hardest part.
    # In a real app, you'd use `python-telegram-bot` library.
    
    # A simplified flow using an external library would be:
    # 1. Bot receives message_id
    # 2. bot.get_file(message_id) -> returns File object
    # 3. file.download_as_bytearray() -> returns bytes
    # We will simulate this. For this code to work, you need a more advanced setup.
    # Let's assume a simplified direct download for now, which is not what the API provides.
    # THIS PART WILL NEED A REAL TELEGRAM LIBRARY LIKE `python-telegram-bot`
    # For now, we'll code the logic flow.

    # This is a conceptual placeholder. The download logic is actually more complex.
    # You would typically get a file_path and then construct the download URL.
    # This service is a major point of research for a production app.
    # We will proceed with the logical structure. The `download_chunk_from_telegram`
    # would need to be implemented robustly.
    pass

async def delete_messages_from_telegram(message_ids: List[int]):
    async with httpx.AsyncClient() as client:
        for mid in message_ids:
            url = f"{TELEGRAM_API_URL}/deleteMessage"
            params = {'chat_id': settings.TELEGRAM_CHANNEL_ID, 'message_id': mid}
            await client.get(url, params=params)
            print(f"Deleted message {mid} from Telegram")