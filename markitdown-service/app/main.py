# app/main.py
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded

from app.api.v1.endpoints import conversion
from app.core.security.api_key import get_api_key
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import get_db
from app.utils.audit import audit_log

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    try:
        logger.info("Initializing database...")
        db = next(get_db())
        init_db(db)
        logger.info("Database initialized successfully")
        
        # Log startup configuration
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"API Key Auth Enabled: {settings.API_KEY_AUTH_ENABLED}")
        logger.info(f"Rate Limit: {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW} seconds")
        
        # Audit log startup
        audit_log(
            action="service_startup",
            user_id=None,
            details=f"Service started in {settings.ENVIRONMENT} environment"
        )
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        audit_log(
            action="service_startup",
            user_id=None,
            details=f"Service startup failed: {str(e)}",
            status="failure"
        )
        raise
    
    yield  # Server is running
    
    # Shutdown
    logger.info("Application shutting down...")
    audit_log(
        action="service_shutdown",
        user_id=None,
        details="Service shutdown initiated"
    )

# Initialize FastAPI app with lifespan (no global API key dependency)
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A service for converting various file formats to Markdown",
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

# Custom rate limit exceeded handler
@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request, exc):
    """Handle rate limit exceeded exceptions."""
    audit_log(
        action="rate_limit_exceeded",
        user_id=None,
        details=f"Rate limit exceeded for IP: {get_remote_address(request)}",
        status="failure"
    )
    
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded",
            "type": "rate_limit_exceeded"
        },
        headers={
            "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time() + settings.RATE_LIMIT_WINDOW)),
            "Retry-After": str(settings.RATE_LIMIT_WINDOW)
        }
    )

# Include routers with API key dependency
app.include_router(
    conversion.router,
    prefix=settings.API_V1_STR,
    tags=["conversion"],
    dependencies=[Depends(get_api_key)] if settings.API_KEY_AUTH_ENABLED else None
)

# Health check endpoint (no API key required)
@app.get("/health", tags=["system"])
async def health_check():
    """Check the health of the service."""
    try:
        # Verify database connection
        db = next(get_db())
        db.execute("SELECT 1")  # Simple query to check database connection
        
        health_status = {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "auth_enabled": settings.API_KEY_AUTH_ENABLED,
            "supported_formats": settings.SUPPORTED_EXTENSIONS,
            "database": "connected",
            "rate_limit": {
                "requests": settings.RATE_LIMIT_REQUESTS,
                "window": settings.RATE_LIMIT_WINDOW
            }
        }
        
        audit_log(
            action="health_check",
            user_id=None,
            details="Health check successful"
        )
        
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        
        audit_log(
            action="health_check",
            user_id=None,
            details=f"Health check failed: {str(e)}",
            status="failure"
        )
        
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "version": settings.VERSION,
                "error": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
        workers=1
    )