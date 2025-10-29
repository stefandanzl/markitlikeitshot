import time
import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import os
from pathlib import Path
from app.api.v1.endpoints import conversion, admin
from app.core.security.api_key import get_api_key
from app.db.init_db import ensure_db_initialized
from app.db.session import get_db, get_db_session
from app.core.config.settings import settings
from app.core.logging.config import get_web_logging_config
from app.core.audit import audit_log, AuditAction
from app.core.logging.management import LogManager
from app.core.rate_limiting.middleware import RateLimitMiddleware
from app.core.errors.handlers import handle_api_operation

# Initialize logging
log_dir = Path(settings.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)

# Initialize log manager
log_manager = LogManager()

# Configure logging
logging.config.dictConfig(get_web_logging_config())

# Create module-specific loggers
logger = logging.getLogger(__name__)
api_logger = logging.getLogger("app.api")
db_logger = logging.getLogger("app.db")
security_logger = logging.getLogger("app.core.security")

# Global exception handler
@handle_api_operation("global_exception_handler")
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

# Request Validation Error Handler
@handle_api_operation("validation_exception_handler")
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Request validation failed", extra={"errors": exc.errors(), "body": exc.body})
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request parameters", "errors": exc.errors()}
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    try:
        logger.info("Starting application initialization...")
        
        # Ensure log directory is properly set up
        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log detailed configuration in debug mode
        logger.debug("Application configuration:")
        logger.debug(f"Environment: {settings.ENVIRONMENT}")
        logger.debug(f"Log Level: {settings.LOG_LEVEL}")
        logger.debug(f"API Key Auth: {settings.API_KEY_AUTH_ENABLED}")
        logger.debug(f"Log Directory: {settings.LOG_DIR}")
        
        # Initialize database
        logger.info("Initializing database...")
        ensure_db_initialized()
        
        # Check log rotation configuration
        if settings.ENVIRONMENT in ["production", "development"]:
            try:
                logrotate_config = Path("/etc/logrotate.d/markitdown")
                if not logrotate_config.exists():
                    logger.warning("Logrotate configuration not found")
            except Exception as e:
                logger.warning(f"Failed to check logrotate configuration: {e}")
        
        # Log startup status
        logger.info(f"Application started successfully in {settings.ENVIRONMENT} mode")

        # Audit log startup with detailed environment info
        audit_log(
            action=AuditAction.SERVICE_STARTUP,
            user_id=None,
            details={
                "environment": settings.ENVIRONMENT,
                "log_level": settings.LOG_LEVEL,
                "api_auth_enabled": settings.API_KEY_AUTH_ENABLED,
                "version": settings.VERSION,
                "log_dir": str(log_dir),
                "log_rotation": settings.LOG_ROTATION
            }
        )
        
    except Exception as e:
        logger.critical(f"Failed to initialize application: {str(e)}", exc_info=True)
        audit_log(
            action=AuditAction.SERVICE_STARTUP,
            user_id=None,
            details={"error": str(e)},
            status="failure"
        )
        raise
    
    yield  # Server is running
    
    # Shutdown
    logger.info("Initiating application shutdown...")
    try:
        # Ensure all logs are flushed
        for handler in logging.getLogger().handlers:
            handler.flush()
        
        audit_log(
            action=AuditAction.SERVICE_SHUTDOWN,
            user_id=None,
            details={"shutdown_type": "graceful"}
        )
        logger.info("Application shutdown completed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
        audit_log(
            action=AuditAction.SERVICE_SHUTDOWN,
            user_id=None,
            details={"error": str(e)},
            status="failure"
        )

# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A service for converting various file formats to Markdown",
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan
)

# Add rate limiting
app.add_middleware(RateLimitMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

# Add exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers with API key dependency
app.include_router(
    conversion.router,
    prefix=settings.API_V1_STR,
    tags=["conversion"],
    dependencies=[Depends(get_api_key)] if settings.API_KEY_AUTH_ENABLED else None
)

# Public conversion endpoint for frontend (no API key required)
from fastapi import UploadFile, File, status
from fastapi.responses import PlainTextResponse, Response

@app.post(
    "/public/api/v1/convert/file",
    response_class=PlainTextResponse,
    tags=["public-conversion"]
)
@handle_api_operation(
    "public_convert_file",
    error_map={
        "ConversionError": (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
        "RateLimitExceeded": (status.HTTP_429_TOO_MANY_REQUESTS, None),
        **conversion.DEFAULT_ERROR_MAP
    }
)
async def public_convert_file(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
) -> PlainTextResponse:
    """Convert an uploaded file to markdown (public endpoint)."""
    # Import required modules
    from app.core.security.api_key import get_api_key_from_string

    # Apply rate limiting
    await conversion.rate_limit(
        rate=settings.RATE_LIMITS["/api/v1/convert/file"]["rate"],
        per=settings.RATE_LIMITS["/api/v1/convert/file"]["per"]
    )(request, response)

    # Use dev admin key for public requests
    api_key = get_api_key_from_string("dev-admin-key")

    ext, content = await conversion.validate_upload_file(file=file)

    conversion.log_conversion_attempt(
        "file",
        {
            "filename": file.filename,
            "content_type": file.content_type,
            "extension": ext,
        },
        str(api_key.id) if api_key else "public"
    )

    with conversion.save_temp_file(content, suffix=ext) as temp_file_path:
        markdown_content = conversion.process_conversion(
            temp_file_path,
            ext,
            content_type=file.content_type
        )

        return PlainTextResponse(
            content=markdown_content,
            status_code=status.HTTP_200_OK
        )

# Include admin router with API key dependency
app.include_router(
    admin.router,
    prefix=settings.API_V1_STR,
    dependencies=[Depends(get_api_key)] if settings.API_KEY_AUTH_ENABLED else None
)

# Serve the frontend
@app.get("/", tags=["frontend"])
async def serve_frontend():
    """Serve the main frontend page."""
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path)
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend not found"}
    )

# Health check endpoint (no API key required)
@app.get("/health", tags=["system"])
@handle_api_operation("health_check")
async def health_check():
    """Check the health of the service."""
    try:
        # Verify database connection using context manager
        with get_db_session() as db:
            db.execute(text("SELECT 1"))
            db_logger.debug("Database health check successful")
        
        # Check log directory status
        log_status = "healthy"
        log_error = None
        try:
            log_dir = Path(settings.LOG_DIR)
            if not log_dir.exists():
                log_status = "warning"
                log_error = "Log directory does not exist"
            elif not os.access(log_dir, os.W_OK):
                log_status = "warning"
                log_error = "Log directory not writable"
        except Exception as e:
            log_status = "error"
            log_error = str(e)
        
        health_status = {
            "status": "healthy",
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "auth_enabled": settings.API_KEY_AUTH_ENABLED,
            "supported_formats": settings.SUPPORTED_EXTENSIONS,
            "database": "connected",
            "logging": {
                "status": log_status,
                "directory": str(log_dir),
                "error": log_error
            },
            "rate_limiting": {
                "enabled": settings.RATE_LIMITING_ENABLED,
                "default_rate": settings.RATE_LIMIT_DEFAULT_RATE
            },
            "api_key_auth": {
                "enabled": settings.API_KEY_AUTH_ENABLED,
                "header_name": settings.API_KEY_HEADER_NAME
            }
        }
        
        # Log health check with detailed status in debug mode
        logger.debug("Health check details", extra=health_status)
        
        audit_log(
            action=AuditAction.HEALTH_CHECK,
            user_id=None,
            details=health_status
        )
        
        # If there are any warnings, reflect in response code
        if log_status == "warning":
            return JSONResponse(
                status_code=200,
                content=health_status,
                headers={"X-Health-Warning": "Log system issues detected"}
            )
        
        return health_status
    except Exception as e:
        error_details = {
            "status": "unhealthy",
            "version": settings.VERSION,
            "error": str(e)
        }
        
        logger.error(
            "Health check failed",
            exc_info=True,
            extra=error_details
        )
        
        audit_log(
            action=AuditAction.HEALTH_CHECK,
            user_id=None,
            details=error_details,
            status="failure"
        )
        
        return JSONResponse(
            status_code=503,
            content=error_details
        )

if __name__ == "__main__":
    import uvicorn
    
    # Ensure log directory exists before starting server
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    log_config = get_web_logging_config()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
        log_config=log_config,
        workers=1
    )
