from datetime import datetime, UTC
from typing import Optional, Tuple, Dict, Any, Callable
from fastapi import Request, Response
import time
from collections import defaultdict
import threading
from app.core.config import settings
from app.core.audit import audit_log, AuditAction
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Thread-safe in-memory rate limiter using fixed window algorithm"""
    
    def __init__(self):
        self.buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"requests": 0, "window_start": 0}
        )
        self.lock = threading.Lock()

    def reset(self):
        """Reset all rate limiting buckets"""
        with self.lock:
            self.buckets.clear()
    
    def _get_bucket_key(self, request: Request) -> str:
        """Get unique key for rate limit bucket based on API key or IP"""
        api_key = getattr(request.state, "api_key", None)
        if api_key:
            return f"key_{api_key.id}"
        return f"ip_{request.client.host}"

    def check_rate_limit(
        self, 
        request: Request,
        response: Response,
        rate: int = 30,
        per: int = 60
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited.
        
        Args:
            request: FastAPI request
            response: FastAPI response
            rate: Number of allowed requests
            per: Time period in seconds
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (is_allowed, limit_info)
        """
        bucket_key = self._get_bucket_key(request)
        now = int(time.time())
        
        with self.lock:
            bucket = self.buckets[bucket_key]
            
            # Check if we're in a new time window
            if now - bucket["window_start"] >= per:
                bucket["requests"] = 0
                bucket["window_start"] = now
            
            # Calculate time left in the current window
            time_passed = now - bucket["window_start"]
            time_left = max(0, per - time_passed)
            reset_time = bucket["window_start"] + per
            
            # Check if we've exceeded the rate limit
            if bucket["requests"] >= rate:
                is_allowed = False
                remaining = 0
            else:
                is_allowed = True
                bucket["requests"] += 1
                remaining = rate - bucket["requests"]
            
            # Prepare rate limit info
            limit_info = {
                "limit": rate,
                "remaining": remaining,
                "reset": reset_time,
                "key": bucket_key,
                "retry_after": time_left
            }
            
            # Log rate limit check
            logger.debug(
                f"Rate limit check: {bucket_key}",
                extra={
                    "allowed": is_allowed,
                    "remaining": remaining,
                    "reset": reset_time,
                    "path": request.url.path
                }
            )
            
            return is_allowed, limit_info

class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded"""
    def __init__(self, limit_info: Dict[str, Any]):
        self.limit_info = limit_info
        super().__init__("Rate limit exceeded")

# Global rate limiter instance
limiter = RateLimiter()

def add_rate_limit_headers(response: Response, limit_info: Dict[str, Any]) -> None:
    """Add standard rate limit headers to response"""
    response.headers.update({
        "X-RateLimit-Limit": str(limit_info["limit"]),
        "X-RateLimit-Remaining": str(limit_info["remaining"]),
        "X-RateLimit-Reset": str(limit_info["reset"]),
        "RateLimit-Policy": f"{limit_info['limit']};w={60}",
        "RateLimit-Limit": str(limit_info["limit"]),
        "RateLimit-Remaining": str(limit_info["remaining"]),
        "RateLimit-Reset": str(limit_info["reset"]),
        "Retry-After": str(limit_info["retry_after"])
    })

def rate_limit(
    rate: int = settings.RATE_LIMIT_DEFAULT_RATE,
    per: int = settings.RATE_LIMIT_DEFAULT_PERIOD,
    endpoints: Optional[set] = None
) -> Callable:
    """
    Rate limiting dependency for FastAPI endpoints.
    """
    def dependency() -> Callable:
        async def rate_limit_dependency(request: Request, response: Response):
            # Skip rate limiting if disabled
            if not settings.RATE_LIMITING_ENABLED:
                return
                
            # Skip if endpoint is in the excluded list
            if any(request.url.path.startswith(excluded) for excluded in settings.RATE_LIMIT_EXCLUDED_ENDPOINTS):
                return

            # Skip if endpoint not in limited set
            if endpoints and request.url.path not in endpoints:
                return
                
            is_allowed, limit_info = limiter.check_rate_limit(
                request,
                response,
                rate=rate,
                per=per
            )
            
            # Always add rate limit headers
            add_rate_limit_headers(response, limit_info)
            
            if not is_allowed:
                # Log rate limit exceeded
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "bucket_key": limit_info["key"],
                        "path": request.url.path,
                        "method": request.method,
                        "limit": limit_info["limit"],
                        "reset": limit_info["reset"]
                    }
                )
                
                # Audit log rate limit exceeded
                try:
                    audit_log(
                        action=AuditAction.RATE_LIMIT_EXCEEDED,  # Use enum value
                        user_id=getattr(request.state, "api_key", {}).get("id"),
                        details={
                            "path": request.url.path,
                            "method": request.method,
                            "limit_info": limit_info
                        }
                    )
                except Exception as e:
                    logger.error(f"Failed to log rate limit exceeded: {str(e)}")
                
                raise RateLimitExceeded(limit_info)
        
        return rate_limit_dependency
    
    return dependency()
