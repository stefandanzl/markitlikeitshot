import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="session")
def client():
    """
    TestClient fixture that can be used across all tests
    """
    return TestClient(app)

@pytest.fixture(scope="session")
def test_file_path():
    """
    Fixture providing the path to test files
    """
    return "test_files/TestDoc.docx"

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limits between tests"""
    from app.main import limiter
    limiter.reset()
    yield