from datetime import datetime
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    created_by: Optional[int] = Field(default=None)