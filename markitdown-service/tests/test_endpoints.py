# These tests will test making calls to the end points on the test container. They are not unit tests
# of the code itself. This is why this suite does not test the rate limiting.
import os
import pytest
from fastapi.testclient import TestClient
from typing import Generator, Dict
import json
from pathlib import Path
from app.main import app
from app.core.config import settings
from app.db.session import get_db_session, get_engine
from app.core.security.api_key import create_api_key
from app.models.auth.api_key import Role, APIKey
from sqlmodel import SQLModel, delete

# Test file path
TEST_FILE_PATH = Path(__file__).parent / "test_files" / "TestDoc.docx"

@pytest.fixture(scope="session", autouse=True)
def init_test_db():
    """Initialize test database"""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

class TestNoAuthAPI:
    """Test API endpoints without authentication required"""
    
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup test environment with API key auth disabled"""
        # Store original setting
        self.original_auth_setting = settings.API_KEY_AUTH_ENABLED
        
        # Disable API key authentication
        settings.API_KEY_AUTH_ENABLED = False
        
        # Create test client
        self.client = TestClient(app)
        
        yield
        
        # Restore original setting
        settings.API_KEY_AUTH_ENABLED = self.original_auth_setting

    def test_health_check(self) -> None:
        """Test health check endpoint"""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["auth_enabled"] is False

    def test_convert_file_no_auth(self) -> None:
        """Test file conversion without authentication"""
        # Ensure test file exists
        assert TEST_FILE_PATH.exists(), f"Test file not found: {TEST_FILE_PATH}"
        
        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("TestDoc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = self.client.post("/api/v1/convert/file", files=files)
        
        assert response.status_code == 200
        assert response.text  # Should contain markdown content
        assert "# " in response.text  # Basic check for markdown headers

    def test_convert_text_no_auth(self) -> None:
        """Test text conversion without authentication"""
        test_html = "<h1>Test Header</h1><p>Test paragraph</p>"
        response = self.client.post(
            "/api/v1/convert/text",
            json={"content": test_html}
        )
        
        assert response.status_code == 200
        assert "# Test Header" in response.text
        assert "Test paragraph" in response.text

    def test_convert_url_bbc_no_auth(self) -> None:
        """Test BBC News URL conversion without authentication"""
        test_url = "https://www.bbc.co.uk/news/articles/c5ygv2y2e1eo"
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url}
        )
        
        assert response.status_code == 200
        content = response.text
        
        # Basic content checks
        assert "# " in content  # Should have at least one heading
        assert "BBC" in content  # Should mention BBC
        assert "Published" in content  # Should have publication date
    
    def test_convert_url_wikipedia_no_auth(self) -> None:
        """Test Wikipedia URL conversion without authentication"""
        test_url = "https://en.wikipedia.org/wiki/Goat"
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url}
        )
        
        assert response.status_code == 200
        content = response.text
        
        # Check main article elements - more flexible assertions
        assert "# Goat" in content
        assert "Domesticated mammal" in content
        assert "Capra hircus" in content
        
        # Check for common Wikipedia sections
        assert any(section in content for section in [
            "## Etymology",
            "## Biology",
            "## Description",
            "## Uses"
        ])

class TestAuthAPI:
    """Test API endpoints with authentication required"""
    
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Setup test environment with API key auth enabled"""
        # Store original setting
        self.original_auth_setting = settings.API_KEY_AUTH_ENABLED
        
        # Enable API key authentication
        settings.API_KEY_AUTH_ENABLED = True
        
        # Create test client
        self.client = TestClient(app)
        
        # Clean up any existing test users
        with get_db_session() as db:
            # Delete existing test users if they exist
            db.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
            db.commit()
            
            # Create test API key
            api_key = create_api_key(
                db=db,
                name="test-user",
                role=Role.USER
            )
            self.api_key = api_key.key
            
            # Create admin API key
            admin_key = create_api_key(
                db=db,
                name="test-admin",
                role=Role.ADMIN
            )
            self.admin_key = admin_key.key
        
        yield
        
        # Cleanup after tests
        with get_db_session() as db:
            db.exec(delete(APIKey).where(APIKey.name.in_(["test-user", "test-admin"])))
            db.commit()
        
        # Restore original setting
        settings.API_KEY_AUTH_ENABLED = self.original_auth_setting

    def test_health_check_auth(self) -> None:
        """Test health check endpoint (should work without auth)"""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["auth_enabled"] is True

    def test_convert_file_no_key(self) -> None:
        """Test file conversion without API key should fail"""
        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("TestDoc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = self.client.post("/api/v1/convert/file", files=files)
        
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]

    def test_convert_file_with_key(self) -> None:
        """Test file conversion with valid API key"""
        headers = {settings.API_KEY_HEADER_NAME: self.api_key}
        
        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("TestDoc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = self.client.post(
                "/api/v1/convert/file",
                files=files,
                headers=headers
            )
        
        assert response.status_code == 200
        assert response.text  # Should contain markdown content
        assert "# " in response.text  # Basic check for markdown headers

    def test_convert_text_with_key(self) -> None:
        """Test text conversion with valid API key"""
        headers = {settings.API_KEY_HEADER_NAME: self.api_key}
        test_html = "<h1>Test Header</h1><p>Test paragraph</p>"
        
        response = self.client.post(
            "/api/v1/convert/text",
            json={"content": test_html},
            headers=headers
        )
        
        assert response.status_code == 200
        assert "# Test Header" in response.text
        assert "Test paragraph" in response.text

    def test_convert_url_bbc_with_key(self) -> None:
        """Test BBC News URL conversion with valid API key"""
        headers = {settings.API_KEY_HEADER_NAME: self.api_key}
        test_url = "https://www.bbc.co.uk/news/articles/c5ygv2y2e1eo"
        
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=headers
        )
        
        assert response.status_code == 200
        content = response.text
        
        # Basic content checks
        assert "# " in content  # Should have at least one heading
        assert "BBC" in content  # Should mention BBC
        assert "Published" in content  # Should have publication date

    def test_convert_url_wikipedia_with_key(self) -> None:
        """Test Wikipedia URL conversion with valid API key"""
        headers = {settings.API_KEY_HEADER_NAME: self.api_key}
        test_url = "https://en.wikipedia.org/wiki/Goat"
        
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=headers
        )
        
        assert response.status_code == 200
        content = response.text
        
        # More flexible content checks
        assert "# Goat" in content
        assert "Domesticated mammal" in content
        assert "Capra hircus" in content

    def test_invalid_api_key(self) -> None:
        """Test using invalid API key"""
        headers = {settings.API_KEY_HEADER_NAME: "invalid-key"}
        test_html = "<h1>Test</h1>"
        
        response = self.client.post(
            "/api/v1/convert/text",
            json={"content": test_html},
            headers=headers
        )
        
        assert response.status_code == 403
        assert response.json()["detail"] in ["Invalid API key", "API key validation failed"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])