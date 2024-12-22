from datetime import datetime, UTC
import secrets
import bcrypt
from typing import Optional
from fastapi import Security, HTTPException, Depends
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from sqlmodel import Session, select
from app.models.auth.api_key import APIKey, Role
from app.models.auth.user import User, UserStatus
from app.core.config import settings
from app.db.session import get_db
import logging
from app.core.audit import audit_log, AuditAction

logger = logging.getLogger(__name__)

# Initialize API key header
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)

def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(settings.API_KEY_LENGTH)

def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    key_bytes = key.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(key_bytes, salt).decode('utf-8')

def verify_key_hash(key: str, hashed_key: str) -> bool:
    """Verify an API key against its hash."""
    key_bytes = key.encode('utf-8')
    hashed_key_bytes = hashed_key.encode('utf-8')
    return bcrypt.checkpw(key_bytes, hashed_key_bytes)

def create_api_key(
    db: Session,
    name: str,
    user_id: int,
    role: Role = Role.USER,
) -> APIKey:
    """Create a new API key."""
    try:
        # Check if user exists and is active
        user = db.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} does not exist")
        if user.status != UserStatus.ACTIVE:
            raise ValueError(f"User {user.name} is not active")

        # Check for existing key with same name for this user
        existing = db.exec(
            select(APIKey).where(
                APIKey.name == name,
                APIKey.user_id == user_id
            )
        ).first()
        
        if existing:
            raise ValueError(f"API key with name '{name}' already exists for this user")

        # Generate and hash the key
        original_key = generate_api_key()
        hashed_key = hash_api_key(original_key)
        
        # Create new API key instance
        api_key = APIKey(
            key=hashed_key,
            name=name,
            role=role,
            user_id=user_id
        )
        
        # Add to session and flush to get the ID
        db.add(api_key)
        db.flush()
        
        # Audit logging
        audit_log(
            action=AuditAction.API_KEY_CREATED,
            user_id=str(user_id),
            details={
                "key_name": name,
                "role": role.value,
                "user_name": user.name
            }
        )
        
        # Create response object with unhashed key
        response_key = APIKey(
            id=api_key.id,
            key=original_key,  # Return the unhashed key
            name=api_key.name,
            role=api_key.role,
            created_at=api_key.created_at,
            user_id=user_id,
            is_active=api_key.is_active,
            last_used=None
        )
        
        return response_key
        
    except Exception as e:
        logger.exception("Failed to create API key")
        raise

def verify_api_key(db: Session, key: str) -> Optional[APIKey]:
    """Verify an API key and update last used timestamp."""
    try:
        # Get all active keys for active users
        api_keys = db.exec(
            select(APIKey)
            .join(User)
            .where(
                APIKey.is_active == True,
                User.status == UserStatus.ACTIVE
            )
        ).all()
        
        for api_key in api_keys:
            if verify_key_hash(key, api_key.key):
                api_key.last_used = datetime.now(UTC)
                db.flush()
                
                # Audit logging
                audit_log(
                    action=AuditAction.API_KEY_USED,
                    user_id=str(api_key.user_id),
                    details={
                        "key_name": api_key.name,
                        "key_id": api_key.id
                    }
                )
                return api_key
        
        return None
        
    except Exception as e:
        logger.exception("Failed to verify API key")
        raise

def deactivate_api_key(
    db: Session,
    key_id: int,
    deactivated_by_user_id: Optional[int] = None
) -> bool:
    """Deactivate an API key."""
    try:
        api_key = db.get(APIKey, key_id)
        if api_key:
            api_key.is_active = False
            db.flush()
            
            # Audit logging
            audit_log(
                action=AuditAction.API_KEY_DEACTIVATED,
                user_id=str(deactivated_by_user_id),
                details={
                    "key_id": key_id,
                    "key_name": api_key.name,
                    "owner_id": api_key.user_id
                }
            )
            return True
        return False
        
    except Exception as e:
        logger.exception(f"Failed to deactivate API key {key_id}")
        raise

def reactivate_api_key(
    db: Session,
    key_id: int,
    reactivated_by_user_id: Optional[int] = None
) -> bool:
    """Reactivate an API key."""
    try:
        api_key = db.get(APIKey, key_id)
        if api_key:
            # Check if user is active before reactivating key
            user = db.get(User, api_key.user_id)
            if not user or user.status != UserStatus.ACTIVE:
                raise ValueError("Cannot reactivate key for inactive user")

            api_key.is_active = True
            db.flush()
            
            # Audit logging
            audit_log(
                action=AuditAction.API_KEY_REACTIVATED,
                user_id=str(reactivated_by_user_id),
                details={
                    "key_id": key_id,
                    "key_name": api_key.name,
                    "owner_id": api_key.user_id
                }
            )
            return True
        return False
        
    except Exception as e:
        logger.exception(f"Failed to reactivate API key {key_id}")
        raise

async def get_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[APIKey]:
    """
    Dependency for validating API keys in FastAPI endpoints.
    Returns None if API key auth is disabled.
    """
    if not settings.API_KEY_AUTH_ENABLED:
        return None
        
    if not api_key:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="API key required"
        )
    
    try:
        key = verify_api_key(db, api_key)
        if not key:
            # Audit logging for failed attempts
            audit_log(
                action=AuditAction.API_KEY_INVALID,
                user_id=None,
                details="Invalid API key attempt",
                status="failure"
            )
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Invalid API key"
            )
        
        return key
        
    except Exception as e:
        logger.exception("API key validation failed")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="API key validation failed"
        )

def require_admin(api_key: APIKey = Depends(get_api_key)):
    """
    Dependency for requiring admin role in FastAPI endpoints.
    Must be used after get_api_key dependency.
    """
    if settings.API_KEY_AUTH_ENABLED and (not api_key or api_key.role != Role.ADMIN):
        # Audit logging for unauthorized admin access attempts
        audit_log(
            action=AuditAction.ADMIN_ACCESS_DENIED,
            user_id=str(api_key.user_id) if api_key else None,
            details="Unauthorized admin access attempt",
            status="failure"
        )
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return api_key