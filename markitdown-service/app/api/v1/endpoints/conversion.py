from fastapi import APIRouter, UploadFile, File, HTTPException, status, Request, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from markitdown import MarkItDown
import tempfile
import os
import logging
import logging.config
import requests
import time
from contextlib import contextmanager
from app.core.config import settings
from app.core.security.api_key import get_api_key, require_admin
from app.core.error_handlers import handle_api_operation, OperationError
from app.utils.audit import audit_log
from app.core.rate_limit import limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# Initialize router
router = APIRouter(tags=["conversion"])

# Initialize module-specific logger
logger = logging.getLogger("app.api.conversion")
perf_logger = logging.getLogger("app.api.conversion.performance")

# Custom exceptions
class FileProcessingError(Exception):
    pass

class ConversionError(Exception):
    pass

# Custom response class for rate limiting
class RateLimitedResponse(PlainTextResponse):
    def __init__(self, content: str, status_code: int = 200, headers: dict = None, **kwargs):
        super().__init__(content, status_code=status_code, **kwargs)
        if headers:
            self.headers.update(headers)

class TextInput(BaseModel):
    content: str
    options: Optional[dict] = None

class UrlInput(BaseModel):
    url: HttpUrl
    options: Optional[dict] = None

def log_conversion_attempt(
    conversion_type: str,
    metadata: Dict[str, Any],
    user_id: Optional[str] = None
) -> None:
    """Log conversion attempt with metadata."""
    # Create a new dict for logging to avoid modifying the original metadata
    log_data = {
        "conversion_type": conversion_type,
        "user_id": user_id,
    }
    
    # Add metadata with safe key names
    for key, value in metadata.items():
        # Avoid using reserved logging field names
        if key == 'filename':
            log_data['input_filename'] = value  # Rename to avoid conflict
        else:
            log_data[key] = value

    logger.info(
        f"{conversion_type} conversion initiated",
        extra=log_data
    )

def log_conversion_result(
    conversion_type: str,
    success: bool,
    duration: float,
    metadata: Dict[str, Any],
    error: Optional[Exception] = None
) -> None:
    """Log conversion result with performance metrics."""
    # Create safe log data
    log_data = {
        "conversion_type": conversion_type,
        "success": success,
        "duration_ms": round(duration * 1000, 2),
    }

    # Add metadata with safe key names
    for key, value in metadata.items():
        # Avoid using reserved logging field names
        if key == 'filename':
            log_data['input_filename'] = value
        else:
            log_data[key] = value

    if error:
        log_data["error"] = str(error)
        log_data["error_type"] = error.__class__.__name__

    # Log to performance logger
    perf_logger.info(
        f"{conversion_type} conversion completed",
        extra=log_data
    )

    # Log to main logger with appropriate level
    if success:
        logger.info(f"{conversion_type} conversion successful", extra=log_data)
    else:
        logger.error(f"{conversion_type} conversion failed", extra=log_data)

@contextmanager
def save_temp_file(content: bytes, suffix: str) -> str:
    """Save content to a temporary file and return the file path."""
    if len(content) > settings.MAX_FILE_SIZE:
        logger.warning(
            "File size limit exceeded",
            extra={
                "size": len(content),
                "limit": settings.MAX_FILE_SIZE
            }
        )
        raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

    with tempfile.NamedTemporaryFile(suffix=suffix, mode='w+b', delete=False) as temp_file:
        try:
            temp_file.write(content)
            temp_file.flush()
            logger.debug(
                "Temporary file created",
                extra={
                    "path": temp_file.name,
                    "size": len(content)
                }
            )
            yield temp_file.name
        finally:
            if os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                    logger.debug(f"Temporary file removed: {temp_file.name}")
                except Exception as e:
                    logger.warning(
                        "Failed to remove temporary file",
                        extra={
                            "path": temp_file.name,
                            "error": str(e)
                        }
                    )

def process_conversion(file_path: str, ext: str, url: Optional[str] = None, content_type: str = None) -> str:
    """Process conversion using MarkItDown and clean the markdown content."""
    start_time = time.time()
    conversion_metadata = {
        "file_extension": ext,
        "url": url,
        "content_type": content_type
    }

    try:
        converter = MarkItDown()
        
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise ConversionError("Input file is empty or does not exist")
            
        if url and "wikipedia.org" in url:
            logger.debug("Using WikipediaConverter for Wikipedia URL")
            result = converter.convert(file_path, file_extension=ext, url=url, converter_type='wikipedia')
        else:
            if ext.lower() == '.html':
                result = converter.convert(file_path, file_extension=ext, converter_type='html')
            else:
                result = converter.convert(file_path, file_extension=ext, url=url)
            
        if not result or not result.text_content:
            raise ConversionError("Conversion resulted in empty content")
        
        duration = time.time() - start_time
        log_conversion_result("content", True, duration, conversion_metadata)
        return result.text_content

    except Exception as e:
        duration = time.time() - start_time
        log_conversion_result("content", False, duration, conversion_metadata, error=e)
        logger.exception(
            "Conversion failed",
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__,
                **conversion_metadata
            }
        )
        raise ConversionError(f"Failed to convert content: {str(e)}")

def get_rate_limit_headers(request: Request) -> dict:
    """Get rate limit headers from request state"""
    now = int(time.time())
    if settings.RATE_LIMIT_PERIOD == "minute":
        window_seconds = 60
    elif settings.RATE_LIMIT_PERIOD == "hour":
        window_seconds = 3600
    else:
        window_seconds = 60  # Default to minute if unknown period
        
    window_reset = now + window_seconds
    
    return {
        "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
        "X-RateLimit-Remaining": str(getattr(request.state, "view_rate_limit_remaining", 0)),
        "X-RateLimit-Reset": str(window_reset),
        "Retry-After": str(window_seconds)
    }

@contextmanager
def error_handler():
    """Context manager for handling conversion errors."""
    try:
        yield None
    except requests.RequestException as e:
        logger.exception(
            "URL fetch error",
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching URL: {str(e)}"
        )
    except FileProcessingError as e:
        logger.warning(
            "File processing error",
            extra={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConversionError as e:
        logger.error(
            "Conversion error",
            extra={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(
            "Unexpected conversion error",
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during conversion"
        )

@router.post("/convert/text", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
@handle_api_operation(
    "convert_text",
    error_map={
        FileProcessingError: (400, "File processing failed"),
        ConversionError: (422, "Conversion failed"),
        requests.RequestException: (502, "Request failed"),
        Exception: (500, "Internal server error")
    }
)
async def convert_text(
    request: Request,
    text_input: TextInput,
    api_key: str = Depends(get_api_key)
):
    """Convert text or HTML to markdown."""
    conversion_metadata = {
        "content_length": len(text_input.content),
        "has_options": bool(text_input.options)
    }
    
    # Process the conversion
    with save_temp_file(text_input.content.encode('utf-8'), suffix='.html') as temp_file_path:
        markdown_content = process_conversion(temp_file_path, '.html')
        headers = get_rate_limit_headers(request)
        return RateLimitedResponse(content=markdown_content, headers=headers)

@router.post("/convert/file", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
@handle_api_operation(
    "convert_file",
    error_map={
        FileProcessingError: (400, "File processing failed"),
        ConversionError: (422, "Conversion failed"),
        requests.RequestException: (502, "Request failed"),
        Exception: (500, "Internal server error")
    }
)
async def convert_file(
    request: Request,
    file: UploadFile = File(...),
    api_key: str = Depends(get_api_key)
):
    """Convert an uploaded file to markdown."""
    # Extract file information
    _, ext = os.path.splitext(file.filename)
    
    # Validate file extension
    if ext.lower() not in settings.SUPPORTED_EXTENSIONS:
        raise FileProcessingError(f"Unsupported file type: {ext}")

    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > settings.MAX_FILE_SIZE:
        raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

    # Process the conversion
    with save_temp_file(content, suffix=ext) as temp_file_path:
        markdown_content = process_conversion(
            temp_file_path,
            ext,
            content_type=file.content_type
        )
        headers = get_rate_limit_headers(request)
        return RateLimitedResponse(content=markdown_content, headers=headers)

@router.post("/convert/url", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
@handle_api_operation(
    "convert_url",
    error_map={
        FileProcessingError: (400, "File processing failed"),
        ConversionError: (422, "Conversion failed"),
        requests.RequestException: (502, "Request fetch failed"),
        Exception: (500, "Internal server error")
    }
)
async def convert_url(
    request: Request,
    url_input: UrlInput,
    api_key: str = Depends(get_api_key)
):
    """Fetch a URL and convert its content to markdown."""
    # Fetch URL content
    headers = {'User-Agent': settings.USER_AGENT}
    response = requests.get(
        str(url_input.url), 
        headers=headers, 
        timeout=settings.REQUEST_TIMEOUT
    )
    response.raise_for_status()
    
    # Process the conversion
    content = response.content
    with save_temp_file(content, suffix='.html') as temp_file_path:
        markdown_content = process_conversion(
            temp_file_path,
            '.html',
            url=str(url_input.url)
        )
        headers = get_rate_limit_headers(request)
        return RateLimitedResponse(content=markdown_content, headers=headers)
