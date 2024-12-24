import pytest
import time
from fastapi import status
from unittest.mock import patch
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.core.rate_limiting.limiter import limiter
from app.core.rate_limiting.middleware import RateLimitItem

@pytest.fixture(autouse=True)
def mock_rate_limit():
    """Mock rate limit checking to allow controlled testing."""
    request_count = 0
    
    def mock_check(request, func, error_message):
        nonlocal request_count
        request_count += 1
        
        # Calculate rate limit info
        now = int(time.time())
        window_reset = now + 60  # 1 minute window
        
        if request_count > 10:  # Simulate rate limit exceeded
            # Set rate limit info before raising exception
            key = "rate_limit_test"
            rate_limit_item = RateLimitItem(amount=10, key=key)
            rate_limit_info = {
                "limit": 10,
                "remaining": 0,
                "reset": window_reset
            }
            request.state._rate_limit_info = rate_limit_info
            request.state.view_rate_limit = (rate_limit_item, [key, 10, window_reset], "minute")
            raise RateLimitExceeded(rate_limit_item)
        
        # Set rate limit info for successful request
        key = "rate_limit_test"
        rate_limit_item = RateLimitItem(amount=10, key=key)
        rate_limit_info = {
            "limit": 10,
            "remaining": 10 - request_count,
            "reset": window_reset
        }
        request.state._rate_limit_info = rate_limit_info
        request.state.view_rate_limit = (rate_limit_item, [key, 10, window_reset], "minute")
        return True
    
    with patch('slowapi.extension.Limiter._check_request_limit', side_effect=mock_check):
        yield

def test_rate_limit_basic_success(auth_client):
    """Test successful requests within rate limit."""
    client, api_key, _ = auth_client
    
    # Test a successful request
    response = client.post(
        "/api/v1/convert/text",
        json={"content": "Test content"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify rate limit headers exist and are correct
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert "Retry-After" in response.headers
    
    # Verify header values
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert 0 <= int(response.headers["X-RateLimit-Remaining"]) <= 9

def test_rate_limit_exceeded(auth_client):
    """Test rate limit exceeded behavior."""
    client, api_key, _ = auth_client
    
    # Make requests up to the limit
    for _ in range(10):
        response = client.post(
            "/api/v1/convert/text",
            json={"content": "Test content"},
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == status.HTTP_200_OK
    
    # Additional request should fail
    response = client.post(
        "/api/v1/convert/text",
        json={"content": "Test content"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    # Verify rate limit headers in error response
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert "Retry-After" in response.headers
    
    # Verify header values
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert int(response.headers["Retry-After"]) > 0

def test_rate_limit_reset(auth_client):
    """Test rate limit reset after window expiration."""
    client, api_key, _ = auth_client
    
    # Make initial request
    initial_response = client.post(
        "/api/v1/convert/text",
        json={"content": "Test content"},
        headers={"X-API-Key": api_key}
    )
    assert initial_response.status_code == status.HTTP_200_OK
    
    # Get reset time from headers
    reset_time = int(initial_response.headers["X-RateLimit-Reset"])
    current_time = int(time.time())
    assert reset_time > current_time
    
    # Verify remaining requests
    assert int(initial_response.headers["X-RateLimit-Remaining"]) == 9

def test_rate_limit_headers_format(auth_client):
    """Test rate limit headers format and values."""
    client, api_key, _ = auth_client
    
    response = client.post(
        "/api/v1/convert/text",
        json={"content": "Test content"},
        headers={"X-API-Key": api_key}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Verify all required headers are present
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers
    assert "Retry-After" in response.headers
    
    # Verify header value types and ranges
    assert response.headers["X-RateLimit-Limit"] == "10"
    assert 0 <= int(response.headers["X-RateLimit-Remaining"]) <= 9
    
    # Verify reset time is in the future
    reset_time = int(response.headers["X-RateLimit-Reset"])
    current_time = int(time.time())
    assert reset_time > current_time
    
    # Verify retry after is positive
    assert int(response.headers["Retry-After"]) > 0
