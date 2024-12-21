import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from typing import Generator, Dict
import os
from pathlib import Path
import tempfile
import responses
import requests
from unittest.mock import patch
from fastapi import status
from app.main import app
from app.core.config import settings
from app.db.session import get_engine, get_db
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role

# Test client fixture
@pytest.fixture
def client(override_get_db) -> Generator:
    """Create test client with overridden database dependency"""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

# API Key fixtures
@pytest.fixture
def test_api_key(test_db) -> str:
    """Create a test API key and return the unhashed key"""
    api_key = create_api_key(
        db=test_db,
        name="test_user",
        role=Role.USER
    )
    test_db.commit()
    return api_key.key

@pytest.fixture
def auth_headers(test_api_key) -> Dict[str, str]:
    """Return headers with API key"""
    return {settings.API_KEY_HEADER_NAME: test_api_key}

# Test data fixtures
@pytest.fixture
def test_text_content() -> str:
    return "<h1>Test Content</h1><p>This is a test.</p>"

@pytest.fixture
def test_file():
    """Create a temporary test HTML file"""
    content = "<html><body><h1>Test File</h1><p>This is a test file.</p></body></html>"
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
        tf.write(content.encode('utf-8'))
        tf.flush()
        yield tf.name
    os.unlink(tf.name)

@pytest.fixture
def mock_url_content():
    """Mock content for URL tests"""
    return "<html><body><h1>Example Domain</h1><p>This is a test page.</p></body></html>"

# Test cases with API auth disabled
class TestEndpointsNoAuth:
    @pytest.fixture(autouse=True)
    def setup_auth(self, monkeypatch):
        """Disable API key authentication for these tests"""
        monkeypatch.setattr(settings, "API_KEY_AUTH_ENABLED", False)

    def test_health_check(self, client: TestClient):
        """Test health check endpoint (should work without auth)"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_convert_text(self, client: TestClient, test_text_content: str):
        """Test text conversion endpoint without auth"""
        response = client.post(
            "/api/v1/convert/text",
            json={"content": test_text_content}
        )
        assert response.status_code == 200
        assert "# Test Content" in response.text
        assert "This is a test." in response.text

    def test_convert_file(self, client: TestClient, test_file: str):
        """Test file conversion endpoint without auth"""
        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/convert/file",
                files={"file": ("test.html", f, "text/html")}
            )
        assert response.status_code == 200
        assert "# Test File" in response.text
        assert "This is a test file." in response.text

    @responses.activate
    def test_convert_url(self, client: TestClient, mock_url_content: str):
        """Test URL conversion endpoint without auth"""
        test_url = "http://example.com"
        responses.add(
            responses.GET,
            test_url,
            body=mock_url_content,
            status=200,
            content_type="text/html"
        )

        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url}
        )
        assert response.status_code == 200
        assert "# Example Domain" in response.text
        assert "This is a test page." in response.text

# Test cases with API auth enabled
class TestEndpointsWithAuth:
    @pytest.fixture(autouse=True)
    def setup_auth(self, monkeypatch):
        """Enable API key authentication for these tests"""
        monkeypatch.setattr(settings, "API_KEY_AUTH_ENABLED", True)

    def test_health_check(self, client: TestClient):
        """Test health check endpoint (should work without auth)"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_convert_text_no_auth(self, client: TestClient, test_text_content: str):
        """Test text conversion endpoint fails without auth"""
        response = client.post(
            "/api/v1/convert/text",
            json={"content": test_text_content}
        )
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]

    def test_convert_text_with_auth(
        self, client: TestClient, test_text_content: str, auth_headers: Dict[str, str]
    ):
        """Test text conversion endpoint succeeds with auth"""
        response = client.post(
            "/api/v1/convert/text",
            json={"content": test_text_content},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "# Test Content" in response.text
        assert "This is a test." in response.text

    def test_convert_file_no_auth(self, client: TestClient, test_file: str):
        """Test file conversion endpoint fails without auth"""
        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/convert/file",
                files={"file": ("test.html", f, "text/html")}
            )
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]

    def test_convert_file_with_auth(
        self, client: TestClient, test_file: str, auth_headers: Dict[str, str]
    ):
        """Test file conversion endpoint succeeds with auth"""
        with open(test_file, "rb") as f:
            response = client.post(
                "/api/v1/convert/file",
                files={"file": ("test.html", f, "text/html")},
                headers=auth_headers
            )
        assert response.status_code == 200
        assert "# Test File" in response.text
        assert "This is a test file." in response.text

    def test_convert_file_invalid_type(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """Test file conversion with unsupported file type"""
        content = "Invalid file content"
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as tf:
            tf.write(content.encode('utf-8'))
            tf.flush()
            with open(tf.name, "rb") as f:
                response = client.post(
                    "/api/v1/convert/file",
                    files={"file": ("test.xyz", f, "application/octet-stream")},
                    headers=auth_headers
                )
        os.unlink(tf.name)
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_convert_url_no_auth(self, client: TestClient):
        """Test URL conversion endpoint fails without auth"""
        test_url = "http://example.com"
        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url}
        )
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]

    @responses.activate
    def test_convert_url_with_auth(
        self, client: TestClient, auth_headers: Dict[str, str], mock_url_content: str
    ):
        """Test URL conversion endpoint succeeds with auth"""
        test_url = "http://example.com"
        responses.add(
            responses.GET,
            test_url,
            body=mock_url_content,
            status=200,
            content_type="text/html"
        )

        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=auth_headers
        )
        assert response.status_code == 200
        assert "# Example Domain" in response.text
        assert "This is a test page." in response.text

    @responses.activate
    def test_convert_url_connection_error(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """Test URL conversion with connection error"""
        test_url = "http://example.com"
        responses.add(
            responses.GET,
            test_url,
            body=requests.exceptions.ConnectionError("Connection refused")
        )

        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Connection refused" in response.json()["detail"]

    @responses.activate
    def test_convert_url_timeout(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """Test URL conversion with timeout error"""
        test_url = "http://example.com"
        responses.add(
            responses.GET,
            test_url,
            body=requests.exceptions.Timeout("Request timed out")
        )

        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_502_BAD_GATEWAY
        assert "Request timed out" in response.json()["detail"]

    @responses.activate
    def test_convert_url_invalid_content_type(
        self, client: TestClient, auth_headers: Dict[str, str]
    ):
        """Test URL conversion with invalid content type"""
        test_url = "http://example.com"
        responses.add(
            responses.GET,
            test_url,
            body="Binary content",
            status=200,
            content_type="application/pdf"
        )

        response = client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Unsupported content type: application/pdf" in response.json()["detail"]