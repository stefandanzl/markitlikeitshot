from datetime import datetime, UTC
from typing import Optional, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    from .user import User

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"

class APIKey(SQLModel, table=True):
    __tablename__ = "api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    name: str
    role: Role
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_used: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    user: Optional["User"] = Relationship(back_populates="api_keys")