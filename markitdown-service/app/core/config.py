# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import List, Optional
import os
from functools import lru_cache

class Settings(BaseSettings):
    # Pydantic V2 configuration
    model_config = ConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8"
    )

    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
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
    RATE_LIMIT_REQUESTS: int = 10     # Number of requests allowed per minute
    RATE_LIMIT_PERIOD: str = "minute" # Rate limit period

    # CORS Settings
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_METHODS: List[str] = ["*"]
    ALLOWED_HEADERS: List[str] = ["*"]

    # Database Settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///./{ENVIRONMENT}_api_keys.db"
    )
    DATABASE_CONNECT_ARGS: dict = {"check_same_thread": False}
    DATABASE_POOL_SIZE: int = 5
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = ENVIRONMENT == "development"

    # API Key Authentication Settings
    API_KEY_AUTH_ENABLED: bool = True
    API_KEY_HEADER_NAME: str = "X-API-Key"
    API_KEY_LENGTH: int = 32
    ADMIN_API_KEY: Optional[str] = os.getenv("ADMIN_API_KEY")
    API_KEY_EXPIRATION_DAYS: Optional[int] = None  # None means no expiration

    # Initial Setup Settings
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "admin@example.com")
    INITIAL_ADMIN_NAME: str = os.getenv("INITIAL_ADMIN_NAME", "System Admin")

    # Security Settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 24

    # Audit Log Settings
    AUDIT_LOG_ENABLED: bool = True
    AUDIT_LOG_FILE: str = f"logs/audit_{ENVIRONMENT}.log"
    AUDIT_LOG_RETENTION_DAYS: int = 90

    # Logging configuration
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = f"logs/app_{ENVIRONMENT}.log"
    LOG_ROTATION: str = "midnight"
    LOG_BACKUP_COUNT: int = 7

    @property
    def LOG_LEVEL(self) -> str:
        if self.ENVIRONMENT == "test":
            return "WARNING"
        elif self.ENVIRONMENT == "production":
            return "INFO"
        return "DEBUG"

    # Database Connection Settings
    @property
    def DATABASE_SETTINGS(self) -> dict:
        return {
            "url": self.DATABASE_URL,
            "connect_args": self.DATABASE_CONNECT_ARGS,
            "pool_size": self.DATABASE_POOL_SIZE,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "echo": self.DATABASE_ECHO,
        }

    # API Documentation Settings
    DOCS_URL: Optional[str] = "/docs" if ENVIRONMENT != "production" else None
    REDOC_URL: Optional[str] = "/redoc" if ENVIRONMENT != "production" else None
    OPENAPI_URL: Optional[str] = "/openapi.json" if ENVIRONMENT != "production" else None

    # CLI Tool Settings
    CLI_COLORS: bool = True
    CLI_TABLE_STYLE: str = "rounded"

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()

settings = get_settings()