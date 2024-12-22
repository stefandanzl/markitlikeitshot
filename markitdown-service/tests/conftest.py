# markitdown-service/tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, delete, Session
from app.main import app
from app.core.config import settings
from app.db.session import get_db_session, get_engine
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role, APIKey

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
        session.close()

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
    
    # Clean up any existing test users
    db_session.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
    db_session.commit()
    
    # Create test API keys
    api_key = create_api_key(
        db=db_session,
        name="test-user",
        role=Role.USER
    )
    admin_key = create_api_key(
        db=db_session,
        name="test-admin",
        role=Role.ADMIN
    )
    db_session.commit()
    
    yield client, api_key.key, admin_key.key
    
    # Cleanup
    db_session.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
    db_session.commit()
    settings.API_KEY_AUTH_ENABLED = original_auth_setting