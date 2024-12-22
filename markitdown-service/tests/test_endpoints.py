# markitdown-service/tests/test_endpoints.py
import os
import pytest
from fastapi.testclient import TestClient
from typing import Generator, Dict
import json
from pathlib import Path
from app.main import app
from app.core.config import settings
from app.models.auth.api_key import Role, APIKey

# Test file path
TEST_FILE_PATH = Path(__file__).parent / "test_files" / "TestDoc.docx"

class TestNoAuthAPI:
    """Test API endpoints without authentication required"""
    
    @pytest.fixture(autouse=True)
    def setup(self, no_auth_client):
        self.client = no_auth_client

    def test_health_check(self) -> None:
        """Test health check endpoint"""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["auth_enabled"] is False

    def test_convert_file_no_auth(self) -> None:
        """Test file conversion without authentication"""
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
        assert "# " in content
        assert "BBC" in content
        assert "Published" in content

    def test_convert_url_wikipedia_no_auth(self) -> None:
        """Test Wikipedia URL conversion without authentication"""
        test_url = "https://en.wikipedia.org/wiki/Goat"
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url}
        )
        
        assert response.status_code == 200
        content = response.text
        assert "# Goat" in content
        assert "Domesticated mammal" in content
        assert "Capra hircus" in content
        assert any(section in content for section in [
            "## Etymology",
            "## Biology",
            "## Description",
            "## Uses"
        ])

class TestAuthAPI:
    """Test API endpoints with authentication required"""
    
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.client, self.api_key, self.admin_key = auth_client
        self.headers = {settings.API_KEY_HEADER_NAME: self.api_key}

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
        with open(TEST_FILE_PATH, "rb") as f:
            files = {"file": ("TestDoc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            response = self.client.post(
                "/api/v1/convert/file",
                files=files,
                headers=self.headers
            )
        
        assert response.status_code == 200
        assert response.text
        assert "# " in response.text

    def test_convert_text_with_key(self) -> None:
        """Test text conversion with valid API key"""
        test_html = "<h1>Test Header</h1><p>Test paragraph</p>"
        response = self.client.post(
            "/api/v1/convert/text",
            json={"content": test_html},
            headers=self.headers
        )
        
        assert response.status_code == 200
        assert "# Test Header" in response.text
        assert "Test paragraph" in response.text

    def test_convert_url_bbc_with_key(self) -> None:
        """Test BBC News URL conversion with valid API key"""
        test_url = "https://www.bbc.co.uk/news/articles/c5ygv2y2e1eo"
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=self.headers
        )
        
        assert response.status_code == 200
        content = response.text
        assert "# " in content
        assert "BBC" in content
        assert "Published" in content

    def test_convert_url_wikipedia_with_key(self) -> None:
        """Test Wikipedia URL conversion with valid API key"""
        test_url = "https://en.wikipedia.org/wiki/Goat"
        response = self.client.post(
            "/api/v1/convert/url",
            json={"url": test_url},
            headers=self.headers
        )
        
        assert response.status_code == 200
        content = response.text
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

    def test_empty_api_key(self) -> None:
        """Test with empty API key"""
        test_html = "<h1>Test</h1>"
        headers = {settings.API_KEY_HEADER_NAME: ""}
        response = self.client.post(
            "/api/v1/convert/text",
            json={"content": test_html},
            headers=headers
        )
        assert response.status_code == 403
        assert "API key required" in response.json()["detail"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])