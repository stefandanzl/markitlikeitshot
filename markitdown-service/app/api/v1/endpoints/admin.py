from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlmodel import Session
from typing import List, Optional
from app.core.security.api_key import verify_api_key, api_key_header
from app.models.auth.api_key import Role, APIKey
from app.models.auth.user import User, UserStatus
from app.core.security.user import create_user, get_user
from app.core.security.api_key import create_api_key
from app.db.session import get_db
from app.core.audit import audit_log, AuditAction
from datetime import datetime
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/admin", tags=["admin"])

# Dependency to verify admin API key
async def verify_admin_api_key(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> APIKey:
    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="API key required"
        )
    
    key = verify_api_key(db, api_key)
    if not key:
        raise HTTPException(
            status_code=403,
            detail="Invalid or inactive API key"
        )
    
    if key.role != Role.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admin role required"
        )
    return key

# Models for request/response
class UserCreate(BaseModel):
    name: str
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    status: str
    created_at: datetime
    api_key_count: int
    active_api_keys: int

class APIKeyCreate(BaseModel):
    name: str
    role: Role
    user_id: int
    description: Optional[str] = None

class APIKeyCreateResponse(BaseModel):
    id: int
    name: str
    key: str  # Included only in creation response
    role: Role
    user_id: int
    user_name: str
    user_status: str
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool

class APIKeyResponse(BaseModel):
    id: int
    name: str
    role: Role
    user_id: int
    user_name: str
    user_status: str
    created_at: datetime
    last_used: Optional[datetime]
    is_active: bool

# User Management Endpoints
@router.post("/users", response_model=UserResponse)
async def create_new_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    _: APIKey = Depends(verify_admin_api_key)
):
    """Create a new user"""
    try:
        new_user = create_user(
            db=db,
            name=user.name,
            email=user.email
        )
        
        db.refresh(new_user)  # Refresh to ensure all fields are populated
        
        return UserResponse(
            id=new_user.id,
            name=new_user.name,
            email=new_user.email,
            status=new_user.status.value,
            created_at=new_user.created_at,
            api_key_count=len(new_user.api_keys),
            active_api_keys=sum(1 for key in new_user.api_keys if key.is_active)
        )
    except Exception as e:
        if "duplicate key value violates unique constraint" in str(e):
            raise HTTPException(status_code=400, detail="Email already exists")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    show_inactive: bool = Query(False, description="Include inactive users"),
    db: Session = Depends(get_db),
    _: APIKey = Depends(verify_admin_api_key)
):
    """List all users"""
    from sqlmodel import select
    query = select(User)
    if not show_inactive:
        query = query.where(User.status == UserStatus.ACTIVE)
    
    users = db.execute(query).scalars().all()
    return [
        UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            status=user.status.value,
            created_at=user.created_at,
            api_key_count=len(user.api_keys),
            active_api_keys=sum(1 for key in user.api_keys if key.is_active)
        )
        for user in users
    ]

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user_info(
    user_id: int,
    db: Session = Depends(get_db),
    _: APIKey = Depends(verify_admin_api_key)
):
    """Get detailed information about a user"""
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        status=user.status.value,
        created_at=user.created_at,
        api_key_count=len(user.api_keys),
        active_api_keys=sum(1 for key in user.api_keys if key.is_active)
    )

@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_admin_api_key)
):
    """Deactivate a user and all their API keys"""
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = UserStatus.INACTIVE
    # Deactivate all API keys
    for key in user.api_keys:
        key.is_active = False
    
    db.commit()
    
    audit_log(
        action=AuditAction.USER_DEACTIVATED,
        user_id=str(api_key.user_id),
        details=f"User {user.id} deactivated by admin"
    )
    
    return {"message": f"Successfully deactivated user {user.name} and all their API keys"}

@router.post("/users/{user_id}/activate")
async def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    api_key: APIKey = Depends(verify_admin_api_key)
):
    """Activate a user (does not reactivate API keys)"""
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.status = UserStatus.ACTIVE
    db.commit()
    
    audit_log(
        action=AuditAction.USER_ACTIVATED,
        user_id=str(api_key.user_id),
        details=f"User {user.id} activated by admin"
    )
    
    return {"message": f"Successfully activated user {user.name}. Note: API keys remain in their current state"}

# API Key Management Endpoints
@router.post("/api-keys", response_model=APIKeyCreateResponse)
async def create_new_api_key(
    api_key_data: APIKeyCreate,
    db: Session = Depends(get_db),
    admin_key: APIKey = Depends(verify_admin_api_key)
):
    """Create a new API key"""
    try:
        api_key = create_api_key(
            db=db,
            name=api_key_data.name,
            role=api_key_data.role,
            user_id=api_key_data.user_id
        )
        
        user = get_user(db, api_key_data.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Commit the changes to the database
        db.commit()
        
        return APIKeyCreateResponse(
            id=api_key.id,
            name=api_key.name,
            key=api_key.key,  # This is the unhashed key
            role=api_key.role,
            user_id=api_key.user_id,
            user_name=user.name,
            user_status=user.status.value,
            created_at=api_key.created_at,
            last_used=api_key.last_used,
            is_active=api_key.is_active
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    show_inactive: bool = Query(False, description="Include inactive keys"),
    db: Session = Depends(get_db),
    _: APIKey = Depends(verify_admin_api_key)
):
    """List all API keys"""
    from sqlmodel import select
    query = select(APIKey)
    if not show_inactive:
        query = query.where(APIKey.is_active == True)
    
    api_keys = db.execute(query).scalars().all()
    return [
        APIKeyResponse(
            id=key.id,
            name=key.name,
            role=key.role,
            user_id=key.user_id,
            user_name=db.get(User, key.user_id).name,
            user_status=db.get(User, key.user_id).status.value,
            created_at=key.created_at,
            last_used=key.last_used,
            is_active=key.is_active
        )
        for key in api_keys
    ]

@router.get("/api-keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key_info(
    key_id: int,
    db: Session = Depends(get_db),
    _: APIKey = Depends(verify_admin_api_key)
):
    """Get detailed information about an API key"""
    api_key = db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    user = get_user(db, api_key.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Associated user not found")
    
    return APIKeyResponse(
        id=api_key.id,
        name=api_key.name,
        role=api_key.role,
        user_id=api_key.user_id,
        user_name=user.name,
        user_status=user.status.value,
        created_at=api_key.created_at,
        last_used=api_key.last_used,
        is_active=api_key.is_active
    )

@router.post("/api-keys/{key_id}/deactivate")
async def deactivate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    admin_key: APIKey = Depends(verify_admin_api_key)
):
    """Deactivate an API key"""
    api_key = db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    if not api_key.is_active:
        return {"message": f"API key '{api_key.name}' is already inactive"}
    
    api_key.is_active = False
    db.commit()
    
    audit_log(
        action=AuditAction.API_KEY_DEACTIVATED,
        user_id=str(admin_key.user_id),
        details=f"API key {key_id} deactivated by admin"
    )
    
    return {"message": f"Successfully deactivated API key: {api_key.name}"}

@router.post("/api-keys/{key_id}/reactivate")
async def reactivate_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    admin_key: APIKey = Depends(verify_admin_api_key)
):
    """Reactivate an API key"""
    api_key = db.get(APIKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = True
    db.commit()
    
    audit_log(
        action=AuditAction.API_KEY_REACTIVATED,
        user_id=str(admin_key.user_id),
        details=f"API key {key_id} reactivated by admin"
    )
    
    return {"message": f"Successfully reactivated API key: {api_key.name}"}
