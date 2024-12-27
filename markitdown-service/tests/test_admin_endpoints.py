import pytest
from fastapi.testclient import TestClient
from typing import Dict
from datetime import datetime
from app.models.auth.api_key import Role
from app.models.auth.user import UserStatus
from app.core.config import settings
from app.core.rate_limiting.limiter import limiter

class TestAdminAPI:
    """Test admin API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self, auth_client):
        self.client, self.api_key, self.admin_key = auth_client
        self.admin_headers = {settings.API_KEY_HEADER_NAME: self.admin_key}
        self.non_admin_headers = {settings.API_KEY_HEADER_NAME: self.api_key}
        settings.RATE_LIMITING_ENABLED = True
        self.original_rate = settings.RATE_LIMIT_DEFAULT_RATE
        self.original_period = settings.RATE_LIMIT_DEFAULT_PERIOD
        self.original_limits = settings.RATE_LIMITS.copy()
        settings.RATE_LIMIT_DEFAULT_RATE = 5
        settings.RATE_LIMIT_DEFAULT_PERIOD = 5
        settings.RATE_LIMITS = {k: {"rate": 5, "per": 5} for k in settings.RATE_LIMITS}
        limiter.reset()

    def teardown_method(self, method):
        settings.RATE_LIMITING_ENABLED = True
        settings.RATE_LIMIT_DEFAULT_RATE = self.original_rate
        settings.RATE_LIMIT_DEFAULT_PERIOD = self.original_period
        settings.RATE_LIMITS = self.original_limits
        limiter.reset()

    def test_admin_access_with_non_admin_key(self) -> None:
        """Test accessing admin endpoints with non-admin API key"""
        response = self.client.get(
            "/api/v1/admin/users",
            headers=self.non_admin_headers
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin role required"

    def test_admin_access_with_invalid_key(self) -> None:
        """Test accessing admin endpoints with invalid API key"""
        headers = {settings.API_KEY_HEADER_NAME: "invalid-key"}
        response = self.client.get("/api/v1/admin/users", headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid or inactive API key"

    def test_admin_access_without_key(self) -> None:
        """Test accessing admin endpoints without API key"""
        response = self.client.get("/api/v1/admin/users")
        assert response.status_code == 403
        assert response.json()["detail"] == "API key required"

    # User Management Tests
    def test_create_user(self) -> None:
        """Test user creation"""
        user_data = {
            "name": "Test User",
            "email": "test_create_user@example.com"
        }
        response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == user_data["name"]
        assert data["email"] == user_data["email"]
        assert data["status"] == UserStatus.ACTIVE.value
        assert "created_at" in data
        assert "api_key_count" in data
        assert "active_api_keys" in data
        assert isinstance(data["id"], int)

    def test_create_user_duplicate_email(self) -> None:
        """Test creating user with duplicate email"""
        user_data = {
            "name": "Test User",
            "email": "test_duplicate@example.com"
        }
        # Create first user
        self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        # Try creating second user with same email
        response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        assert response.status_code == 400
        assert "email already exists" in response.json()["detail"].lower()

    def test_list_users(self) -> None:
        """Test listing users"""
        # Create test users
        users = [
            {"name": "User 1", "email": "user1@example.com"},
            {"name": "User 2", "email": "user2@example.com"}
        ]
        for user in users:
            self.client.post(
                "/api/v1/admin/users",
                json=user,
                headers=self.admin_headers
            )

        # Test listing all users
        response = self.client.get(
            "/api/v1/admin/users",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # May include other users from fixtures
        assert any(u["email"] == "user1@example.com" for u in data)
        assert any(u["email"] == "user2@example.com" for u in data)

    def test_get_user(self) -> None:
        """Test getting user details"""
        # Create test user with unique email
        user_data = {
            "name": "Test User",
            "email": "test_get_user@example.com"
        }
        create_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = create_response.json()["id"]

        # Get user details
        response = self.client.get(
            f"/api/v1/admin/users/{user_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["name"] == user_data["name"]
        assert data["email"] == user_data["email"]

    def test_get_nonexistent_user(self) -> None:
        """Test getting details of non-existent user"""
        response = self.client.get(
            "/api/v1/admin/users/99999",
            headers=self.admin_headers
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_user_deactivation_activation(self) -> None:
        """Test user deactivation and activation"""
        # Create test user with unique email
        user_data = {
            "name": "Test User",
            "email": "test_deactivation@example.com"
        }
        create_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = create_response.json()["id"]

        # Deactivate user
        response = self.client.post(
            f"/api/v1/admin/users/{user_id}/deactivate",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        # Verify user is inactive
        user_response = self.client.get(
            f"/api/v1/admin/users/{user_id}",
            headers=self.admin_headers
        )
        assert user_response.json()["status"] == UserStatus.INACTIVE.value

        # Activate user
        response = self.client.post(
            f"/api/v1/admin/users/{user_id}/activate",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        
        # Verify user is active
        user_response = self.client.get(
            f"/api/v1/admin/users/{user_id}",
            headers=self.admin_headers
        )
        assert user_response.json()["status"] == UserStatus.ACTIVE.value

    # API Key Management Tests
    def test_create_api_key(self) -> None:
        """Test API key creation"""
        # Create test user first with unique email
        user_data = {
            "name": "Test User",
            "email": "test_create_key@example.com"
        }
        user_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = user_response.json()["id"]

        # Create API key
        key_data = {
            "name": "Test Key",
            "role": Role.USER.value,
            "user_id": user_id,
            "description": "Test key description"
        }
        response = self.client.post(
            "/api/v1/admin/api-keys",
            json=key_data,
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == key_data["name"]
        assert data["role"] == key_data["role"]
        assert data["user_id"] == key_data["user_id"]
        assert data["user_name"] == user_data["name"]
        assert "key" in data  # Should include the actual API key in creation response
        assert data["is_active"] is True

    def test_list_api_keys(self) -> None:
        """Test listing API keys"""
        # Create test user with unique email
        user_data = {
            "name": "Test User",
            "email": "test_list_keys@example.com"
        }
        user_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = user_response.json()["id"]

        # Create multiple API keys
        keys = [
            {"name": "Key 1", "role": Role.USER.value, "user_id": user_id},
            {"name": "Key 2", "role": Role.USER.value, "user_id": user_id}
        ]
        for key in keys:
            self.client.post(
                "/api/v1/admin/api-keys",
                json=key,
                headers=self.admin_headers
            )

        # List all keys
        response = self.client.get(
            "/api/v1/admin/api-keys",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # May include other keys from fixtures
        assert any(k["name"] == "Key 1" for k in data)
        assert any(k["name"] == "Key 2" for k in data)

    def test_get_api_key(self) -> None:
        """Test getting API key details"""
        # Create test user with unique email
        user_data = {
            "name": "Test User",
            "email": "test_get_key@example.com"
        }
        user_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = user_response.json()["id"]

        # Create API key
        key_data = {
            "name": "Test Key",
            "role": Role.USER.value,
            "user_id": user_id
        }
        create_response = self.client.post(
            "/api/v1/admin/api-keys",
            json=key_data,
            headers=self.admin_headers
        )
        key_id = create_response.json()["id"]

        # Get key details
        response = self.client.get(
            f"/api/v1/admin/api-keys/{key_id}",
            headers=self.admin_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == key_id
        assert data["name"] == key_data["name"]
        assert data["role"] == key_data["role"]
        assert data["user_id"] == key_data["user_id"]
        assert "key" not in data  # Should not include actual API key in get response

    def test_api_key_deactivation_reactivation(self) -> None:
        """Test API key deactivation and reactivation"""
        # Create test user with unique email
        user_data = {
            "name": "Test User",
            "email": "test_key_deactivation@example.com"
        }
        user_response = self.client.post(
            "/api/v1/admin/users",
            json=user_data,
            headers=self.admin_headers
        )
        user_id = user_response.json()["id"]

        # Create API key
        key_data = {
            "name": "Test Key",
            "role": Role.USER.value,
            "user_id": user_id
        }
        create_response = self.client.post(
            "/api/v1/admin/api-keys",
            json=key_data,
            headers=self.admin_headers
        )
        key_id = create_response.json()["id"]

        # Deactivate key
        response = self.client.post(
            f"/api/v1/admin/api-keys/{key_id}/deactivate",
            headers=self.admin_headers
        )
        assert response.status_code == 200

        # Verify key is inactive
        key_response = self.client.get(
            f"/api/v1/admin/api-keys/{key_id}",
            headers=self.admin_headers
        )
        assert key_response.json()["is_active"] is False

        # Reactivate key
        response = self.client.post(
            f"/api/v1/admin/api-keys/{key_id}/reactivate",
            headers=self.admin_headers
        )
        assert response.status_code == 200

        # Verify key is active
        key_response = self.client.get(
            f"/api/v1/admin/api-keys/{key_id}",
            headers=self.admin_headers
        )
        assert key_response.json()["is_active"] is True

    def test_admin_endpoints_not_rate_limited(self):
        """Test that admin endpoints are not rate limited"""
        # Use test-specific rate limit + 1 to ensure we're over the limit
        requests_count = settings.TEST_RATE_LIMIT_DEFAULT_RATE + 1
        for i in range(requests_count):
            response = self.client.get(
                "/api/v1/admin/users",
                headers=self.admin_headers
            )
            assert response.status_code == 200, f"Admin endpoint should not be rate limited. Got status code: {response.status_code} on request {i+1}"

    def test_create_user_not_rate_limited(self):
        """Test that user creation is not rate limited"""
        # Use test-specific rate limit + 1 to ensure we're over the limit
        requests_count = settings.TEST_RATE_LIMIT_DEFAULT_RATE + 1
        for i in range(requests_count):
            user_data = {
                "name": f"Test User {i}",
                "email": f"test_user_{i}@example.com"
            }
            response = self.client.post(
                "/api/v1/admin/users",
                json=user_data,
                headers=self.admin_headers
            )
            assert response.status_code == 200, f"User creation should not be rate limited. Got status code: {response.status_code} on request {i+1}"

    def teardown_method(self, method):
        settings.RATE_LIMITING_ENABLED = True
        settings.RATE_LIMIT_DEFAULT_RATE = self.original_rate
        settings.RATE_LIMIT_DEFAULT_PERIOD = self.original_period
        settings.RATE_LIMITS = self.original_limits
        limiter.reset()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
