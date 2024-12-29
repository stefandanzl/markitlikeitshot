# app/core/rate_limiting/middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.core.rate_limiting.limiter import RateLimitExceeded, limiter, rate_limit
from fastapi.responses import JSONResponse
import time
import logging
from app.core.config.settings import settings

logger = logging.getLogger(__name__)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMITING_ENABLED:
            return await call_next(request)

        path = request.url.path
        
        # Check if the path is excluded from rate limiting
        if any(path.startswith(excluded) for excluded in settings.RATE_LIMIT_EXCLUDED_ENDPOINTS):
            return await call_next(request)

        # Get endpoint-specific limits from settings
        rate_limits = next(
            (limits for defined_path, limits in settings.RATE_LIMITS.items() if path.startswith(defined_path)),
            {
                "rate": settings.RATE_LIMIT_DEFAULT_RATE,
                "per": settings.RATE_LIMIT_DEFAULT_PERIOD
            }
        )

        # Apply rate limiting
        response = Response()
        is_allowed, limit_info = limiter.check_rate_limit(
            request,
            response,
            rate=rate_limits["rate"],
            per=rate_limits["per"]
        )

        # If rate limit is exceeded, return 429 response
        if not is_allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": limit_info["retry_after"]
                },
                headers={
                    "X-RateLimit-Limit": str(limit_info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(limit_info["reset"]),
                    "Retry-After": str(limit_info["retry_after"])
                }
            )

        # If rate limiting passes, proceed with the request
        response = await call_next(request)
        
        # Set rate limit headers for all responses
        response.headers["X-RateLimit-Limit"] = str(limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(limit_info["reset"])
        
        return response
