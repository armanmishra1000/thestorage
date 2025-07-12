from typing import Optional
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str
    DATABASE_NAME: str = "directdrive"

    # API Configuration
    API_HOST: str = "api.mfcnextgen.com"
    PORT: int = 5000
    CORS_ORIGINS: str = "*"

    # JWT (disabled but kept for future use)
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Hetzner Storage-Box WebDAV
    HETZNER_HOST: str
    HETZNER_USER: str
    HETZNER_PASSWORD: str
    HETZNER_BASE_PATH: str = "/"
    
    # Download configuration
    DOWNLOAD_DOMAIN: str = "dl.mfcnextgen.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Set this to make sure the credential path is relative to the project root
        # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')


settings = Settings()