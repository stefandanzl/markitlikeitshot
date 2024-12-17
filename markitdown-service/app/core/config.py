from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "MarkItDown API"
    VERSION: str = "1.0.0"
    
    # File Processing Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB default
    SUPPORTED_EXTENSIONS: List[str] = [
        '.pdf', '.docx', '.pptx', '.xlsx', '.wav', '.mp3',
        '.jpg', '.jpeg', '.png', '.html', '.htm', '.txt', '.csv', '.json', '.xml'
    ]
    
    # Request Settings
    REQUEST_TIMEOUT: int = 10  # seconds
    USER_AGENT: str = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/91.0.4472.124 Safari/537.36'
    )

    # Rate Limiting Settings
    RATE_LIMIT_REQUESTS: int = 120  # Updated to 120 requests
    RATE_LIMIT_WINDOW: int = 3600  # 1 hour

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_METHODS: List[str] = ["*"]
    ALLOWED_HEADERS: List[str] = ["*"]

    # Logging configuration
    LOG_LEVEL: str = "DEBUG"
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()