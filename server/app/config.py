from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    ENV: str = "dev"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Gemini
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"

    # Whisper
    WHISPER_MODEL_SIZE: str = "base"
    WHISPER_DEVICE: str = "auto"

    # TTS
    TTS_BACKEND: str = "pyttsx3"
    TTS_VOICE: str = "default"
    TTS_RATE: int = 0

    # Media directory
    MEDIA_DIR: str = "./media"   # default fallback

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# ensure the media dir exists
os.makedirs(settings.MEDIA_DIR, exist_ok=True)
