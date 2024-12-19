from datetime import datetime, UTC  # Add UTC import
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"

class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    name: str
    role: Role
    # Update this line to use datetime.now(UTC)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None)