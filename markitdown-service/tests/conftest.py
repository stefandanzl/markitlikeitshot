# markitdown-service/tests/conftest.py
import pytest
from app.core.config import settings
import os
from sqlmodel import SQLModel, Session
from app.db.session import get_engine, get_db
from typing import Generator
import asyncio

def pytest_configure(config):
    """Configure pytest options."""
    # Set asyncio mode in the ini section
    config.inicfg['asyncio_mode'] = 'strict'
    config.inicfg['asyncio_default_fixture_loop_scope'] = 'function'

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Setup test environment variables"""
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/test.db")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("API_KEY_AUTH_ENABLED", "true")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")

@pytest.fixture(scope="function")
def test_db() -> Generator:
    """Create test database tables and cleanup after test"""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    
    # Create a new session for the test
    with Session(engine) as session:
        yield session
    
    # Clean up after test
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def override_get_db(test_db):
    """Override the get_db dependency for testing"""
    def _get_test_db():
        yield test_db
    
    return _get_test_db