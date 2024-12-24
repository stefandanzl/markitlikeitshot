import os
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import SQLModel, delete, Session, select
from app.main import app
from app.core.config import settings
from app.db.session import get_db_session, get_engine
from app.core.security.api_key import create_api_key
from app.core.security.user import create_user
from app.models.auth.api_key import Role, APIKey
from app.models.auth.user import User, UserStatus

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Initialize test database"""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def db_session():
    """Provide a database session for tests"""
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
async def async_client() -> AsyncGenerator:
    """Async client for testing async endpoints"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def test_data_dir() -> str:
    """Provide path to test data directory"""
    return os.path.join(os.path.dirname(__file__), "test_files")

@pytest.fixture
def no_auth_client():
    """Setup test environment with API key auth disabled"""
    original_auth_setting = settings.API_KEY_AUTH_ENABLED
    settings.API_KEY_AUTH_ENABLED = False
    client = TestClient(app)
    yield client
    settings.API_KEY_AUTH_ENABLED = original_auth_setting

@pytest.fixture
def auth_client(db_session):
    """Setup test environment with API key auth enabled"""
    original_auth_setting = settings.API_KEY_AUTH_ENABLED
    settings.API_KEY_AUTH_ENABLED = True
    client = TestClient(app)
    
    # Clean up any existing test users and keys
    db_session.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
    db_session.exec(delete(User).where(User.email.in_(["test-user@example.com", "test-admin@example.com"])))
    db_session.commit()
    
    # Create test users
    test_user = create_user(
        db=db_session,
        name="Test User",
        email="test-user@example.com"
    )
    
    admin_user = create_user(
        db=db_session,
        name="Test Admin",
        email="test-admin@example.com"
    )
    
    # Create test API keys
    api_key = create_api_key(
        db=db_session,
        name="test-user",
        role=Role.USER,
        user_id=test_user.id
    )
    
    admin_key = create_api_key(
        db=db_session,
        name="test-admin",
        role=Role.ADMIN,
        user_id=admin_user.id
    )
    
    db_session.commit()
    
    yield client, api_key.key, admin_key.key
    
    # Cleanup
    db_session.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
    db_session.exec(delete(User).where(User.email.in_(["test-user@example.com", "test-admin@example.com"])))
    db_session.commit()
    settings.API_KEY_AUTH_ENABLED = original_auth_setting
