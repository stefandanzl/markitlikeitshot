from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from app.core.config.settings import settings

class RateLimitStateMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # Get the current window's reset time
        now = int(time.time())
        window_seconds = 60 if settings.RATE_LIMIT_PERIOD == "minute" else 3600
        window_reset = now + window_seconds

        # Initialize rate limit info if not present
        if not hasattr(request.state, "_rate_limit_info"):
            rate_limit_info = {
                "limit": settings.RATE_LIMIT_REQUESTS,
                "remaining": settings.RATE_LIMIT_REQUESTS - 1,  # Subtract 1 for current request
                "reset": window_reset
            }
            request.state._rate_limit_info = rate_limit_info
            # Set view_rate_limit in slowapi expected format: (limit_data, limit_value, period)
            request.state.view_rate_limit = (rate_limit_info, (settings.RATE_LIMIT_REQUESTS,), settings.RATE_LIMIT_PERIOD)

        # Process the request
        response = await call_next(request)

        # Update rate limit info after processing
        rate_limit_info = request.state._rate_limit_info
        if isinstance(rate_limit_info, dict):
            # Ensure remaining count doesn't go below 0
            rate_limit_info["remaining"] = max(0, rate_limit_info["remaining"])
            # Keep view_rate_limit in sync with updated info
            request.state.view_rate_limit = (rate_limit_info, (settings.RATE_LIMIT_REQUESTS,), settings.RATE_LIMIT_PERIOD)

        return response
