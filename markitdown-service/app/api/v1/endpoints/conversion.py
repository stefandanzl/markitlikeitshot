from fastapi import APIRouter, UploadFile, File, HTTPException, status, Request, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
from markitdown import MarkItDown
import tempfile
import os
import logging
import requests
import time
from contextlib import contextmanager
from app.core.config import settings
from app.core.security.api_key import get_api_key, require_admin
from app.utils.audit import audit_log
from app.core.rate_limit import limiter  # Import shared limiter instance
from slowapi.errors import RateLimitExceeded

# Initialize router
router = APIRouter(tags=["conversion"])

# Custom exceptions
class FileProcessingError(Exception):
    pass

class ConversionError(Exception):
    pass

class URLFetchError(Exception):
    pass

# Set up logging
log_level = getattr(logging, settings.LOG_LEVEL)
logging.basicConfig(
    level=log_level,
    format='%(levelname)s:%(name)s:%(message)s' if settings.ENVIRONMENT == "test" else '%(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

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

@contextmanager
def save_temp_file(content: bytes, suffix: str) -> str:
    """Save content to a temporary file and return the file path."""
    if len(content) > settings.MAX_FILE_SIZE:
        raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

    with tempfile.NamedTemporaryFile(suffix=suffix, mode='w+b', delete=False) as temp_file:
        try:
            temp_file.write(content)
            temp_file.flush()
            logger.debug(f"Temporary file created at: {temp_file.name}")
            yield temp_file.name
        finally:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)

def process_conversion(file_path: str, ext: str, url: Optional[str] = None, content_type: str = None) -> str:
    """Process conversion using MarkItDown and clean the markdown content."""
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
            
        return result.text_content
    except Exception as e:
        logger.exception("Conversion failed")
        raise ConversionError(f"Failed to convert content: {str(e)}")

def get_rate_limit_headers(request: Request) -> dict:
    """Get rate limit headers from request state"""
    now = int(time.time())
    window_reset = now + 60  # One minute in seconds
    
    return {
        "X-RateLimit-Limit": str(settings.RATE_LIMIT_REQUESTS),
        "X-RateLimit-Remaining": str(getattr(request.state, "view_rate_limit_remaining", 0)),
        "X-RateLimit-Reset": str(window_reset),
        "Retry-After": "60"  # One minute in seconds
    }

@contextmanager
def error_handler():
    try:
        yield None
    except requests.RequestException as e:
        logger.exception("Error fetching URL")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching URL: {str(e)}"
        )
    except FileProcessingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during text conversion")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during conversion"
        )

@router.post("/convert/text", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
async def convert_text(
    request: Request,
    text_input: TextInput,
    api_key: str = Depends(get_api_key)
):
    """Convert text or HTML to markdown."""
    with error_handler():
        logger.debug(f"Received content: {text_input.content[:100]}...")
        content = text_input.content
        
        # Audit log the conversion attempt
        audit_log(
            action="convert_text",
            user_id=getattr(api_key, 'id', None),
            details=f"Text conversion attempted, length: {len(content)}"
        )
        
        with save_temp_file(content.encode('utf-8'), suffix='.html') as temp_file_path:
            markdown_content = process_conversion(temp_file_path, '.html')
            headers = get_rate_limit_headers(request)
            return RateLimitedResponse(content=markdown_content, headers=headers)

@router.post("/convert/file", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
async def convert_file(
    request: Request,
    file: UploadFile = File(...),
    api_key: str = Depends(get_api_key)
):
    """Convert an uploaded file to markdown."""
    with error_handler():
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in settings.SUPPORTED_EXTENSIONS:
            raise FileProcessingError(f"Unsupported file type: {ext}")

        content = await file.read()
        
        # Audit log the file conversion attempt
        audit_log(
            action="convert_file",
            user_id=getattr(api_key, 'id', None),
            details=f"File conversion attempted: {file.filename}"
        )
        
        if len(content) > settings.MAX_FILE_SIZE:
            raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

        with save_temp_file(content, suffix=ext) as temp_file_path:
            markdown_content = process_conversion(temp_file_path, ext)
            headers = get_rate_limit_headers(request)
            return RateLimitedResponse(content=markdown_content, headers=headers)

@router.post("/convert/url", response_class=RateLimitedResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}")
async def convert_url(
    request: Request,
    url_input: UrlInput,
    api_key: str = Depends(get_api_key)
):
    """Fetch a URL and convert its content to markdown."""
    with error_handler():
        logger.debug(f"Fetching URL: {url_input.url}")
        
        # Audit log the URL conversion attempt
        audit_log(
            action="convert_url",
            user_id=getattr(api_key, 'id', None),
            details=f"URL conversion attempted: {url_input.url}"
        )
        
        headers = {'User-Agent': settings.USER_AGENT}
        
        response = requests.get(
            str(url_input.url), 
            headers=headers, 
            timeout=settings.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        content = response.content
        with save_temp_file(content, suffix='.html') as temp_file_path:
            markdown_content = process_conversion(
                temp_file_path,
                '.html',
                url=str(url_input.url)
            )
            headers = get_rate_limit_headers(request)
            return RateLimitedResponse(content=markdown_content, headers=headers)

# Admin-only endpoint example
@router.get("/stats", dependencies=[Depends(require_admin)])
async def get_conversion_stats():
    """Get conversion statistics (admin only)."""
    return {
        "total_conversions": 0,  # Implement actual stats
        "successful_conversions": 0,
        "failed_conversions": 0
    }