from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    gemini_api_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres@localhost:5432/studyflow"
    chroma_persist_path: str = "./chroma_store"
    upload_dir: str = "./storage/uploads"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Validate required environment variables
if not settings.gemini_api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required")

# Ensure directories exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.chroma_persist_path).mkdir(parents=True, exist_ok=True)
