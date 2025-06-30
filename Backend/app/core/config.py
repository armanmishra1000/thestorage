from typing import Optional
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str
    DATABASE_NAME: str

    # Google Drive
    # GOOGLE_DRIVE_FOLDER_ID: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    
    # NEW: Add the OAuth 2.0 credentials
    GOOGLE_OAUTH_CREDENTIALS_PATH: str
    GOOGLE_OAUTH_REFRESH_TOKEN: str
    GOOGLE_DRIVE_FOLDER_ID: Optional[str] = None

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHANNEL_ID: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    class Config:
        env_file = ".env"
        # Set this to make sure the credential path is relative to the project root
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')


settings = Settings()