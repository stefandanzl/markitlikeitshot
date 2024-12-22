from typing import Optional
import logging
from sqlmodel import Session, select
from app.models.auth.user import User, UserStatus
from app.core.config import settings
from app.core.audit import audit_log, AuditAction

logger = logging.getLogger(__name__)

def create_user(
    db: Session,
    name: str,
    email: str,
    status: UserStatus = UserStatus.ACTIVE,
) -> User:
    """Create a new user."""
    try:
        # Check if email exists
        if db.exec(select(User).where(User.email == email)).first():
            raise ValueError("Email already exists")
        
        # Create user
        user = User(
            name=name,
            email=email,
            status=status
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Audit logging
        audit_log(
            action=AuditAction.USER_CREATED,
            user_id=str(user.id),
            details={
                "name": name,
                "email": email,
                "status": status
            }
        )
        
        return user
        
    except Exception as e:
        logger.exception(f"Failed to create user: {name}")
        raise

def get_user(db: Session, user_id: int) -> Optional[User]:
    """Get a user by ID."""
    return db.get(User, user_id)

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email."""
    return db.exec(select(User).where(User.email == email)).first()

def update_user_status(
    db: Session,
    user_id: int,
    status: UserStatus,
    updated_by: Optional[int] = None
) -> bool:
    """Update a user's status."""
    user = get_user(db, user_id)
    if not user:
        return False
        
    user.status = status
    db.commit()
    
    audit_log(
        action=AuditAction.USER_STATUS_UPDATED,
        user_id=str(updated_by),
        details={
            "target_user": user_id,
            "new_status": status
        }
    )
    
    return True