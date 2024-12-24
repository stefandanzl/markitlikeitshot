from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config.settings import settings

# Initialize rate limiter with settings
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}"],
    strategy="fixed-window",
    storage_uri="memory://",  # Use in-memory storage for rate limiting
    headers_enabled=True,  # Enable rate limit headers
)
