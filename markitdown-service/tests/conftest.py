# tests/conftest.py
import pytest
import logging
import asyncio
from fastapi.testclient import TestClient
from app.main import app, limiter
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(levelname)s: %(message)s'
)
for logger_name in ["httpx", "asyncio", "fastapi", "urllib3"]:
    logging.getLogger(logger_name).setLevel(logging.WARNING)

# Test constants
TEST_WIKI_URL = "https://en.wikipedia.org/wiki/Goat"
TEST_BBC_URL = "https://www.bbc.co.uk/news/articles/c6p229ldn4vo"
TEST_HTML = "<h1>Hello World</h1><p>This is a test</p>"
TEST_DOC_PATH = Path("test_files/TestDoc.docx")

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Reset rate limits between tests"""
    limiter.reset()
    yield
    limiter.reset()  # Clean up after test

@pytest.fixture
def test_doc_path():
    """Fixture to provide test document path"""
    assert TEST_DOC_PATH.exists(), f"Test file not found: {TEST_DOC_PATH}"
    return TEST_DOC_PATH

@pytest.fixture
def client():
    """Test client fixture"""
    with TestClient(app) as client:
        limiter.reset()  # Ensure fresh rate limits
        yield client

@pytest.fixture
def fresh_client():
    """Fresh client for rate limit tests with clean rate limits"""
    with TestClient(app) as client:
        limiter.reset()  # Ensure fresh rate limits
        yield client

@pytest.fixture
def rate_limited_client():
    """Client that's already at rate limit"""
    with TestClient(app) as client:
        limiter.reset()  # Ensure we start fresh
        # Exhaust rate limit
        responses = []
        for _ in range(120):  # Match our rate limit
            response = client.post(
                "/convert/text", 
                json={"content": "<h1>Test</h1>"}
            )
            responses.append(response.status_code)
            if response.status_code == 429:  # Stop if we hit the rate limit
                break
        
        # Verify we actually hit the rate limit
        assert 429 in responses, "Failed to reach rate limit"
        yield client