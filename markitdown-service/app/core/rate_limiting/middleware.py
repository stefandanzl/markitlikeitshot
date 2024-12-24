from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from app.core.config.settings import settings

class RateLimitItem:
    """Class that provides the interface slowapi expects for rate limiting"""
    def __init__(self, amount: int, key: str):
        self.amount = amount
        self.key = key
        self.error_message = f"{amount} per {settings.RATE_LIMIT_PERIOD}"

    def key_for(self, *args):
        return self.key

class RateLimitStateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Get the current window's reset time
        now = int(time.time())
        window_seconds = 60 if settings.RATE_LIMIT_PERIOD == "minute" else 3600
        window_reset = now + window_seconds

        # Initialize rate limit info
        key = f"rate_limit_{request.url.path}"
        rate_limit_item = RateLimitItem(amount=settings.RATE_LIMIT_REQUESTS, key=key)
        
        # Set view_rate_limit in slowapi expected format
        request.state.view_rate_limit = (
            rate_limit_item, 
            [key, settings.RATE_LIMIT_REQUESTS, window_reset],
            settings.RATE_LIMIT_PERIOD
        )

        # Process the request
        response = await call_next(request)

        # Clear any existing rate limit headers to prevent duplicates
        headers_to_set = {
            "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
            "X-RateLimit-Reset": str(window_reset),
            "X-RateLimit-Remaining": str(max(0, settings.RATE_LIMIT_REQUESTS - 1)),
            "Retry-After": str(window_seconds)
        }
        
        # Remove any existing rate limit headers
        for header in headers_to_set.keys():
            if header in response.headers:
                del response.headers[header]
        
        # Set fresh headers
        response.headers.update(headers_to_set)

        return response
