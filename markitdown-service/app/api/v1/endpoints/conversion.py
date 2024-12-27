from fastapi import APIRouter, UploadFile, File, status, Request, Depends, Response
from fastapi.responses import PlainTextResponse
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
from app.core.security.api_key import get_api_key
from app.core.config.settings import settings
from app.core.errors.handlers import handle_api_operation, DEFAULT_ERROR_MAP
from app.core.errors.exceptions import FileProcessingError, ConversionError, ContentTypeError
from app.core.validation.validators import (
    validate_file_size,
    validate_file_extension,
    validate_content_type,
    validate_file_content,
    validate_upload_file,
    validate_text_input
)
from app.core.rate_limiting.limiter import rate_limit, RateLimitExceeded
from app.models.auth.api_key import APIKey  # Add this import

# Initialize router
router = APIRouter(tags=["conversion"])

# Initialize module-specific logger
logger = logging.getLogger("app.api.conversion")
perf_logger = logging.getLogger("app.api.conversion.performance")

class TextInput(BaseModel):
    content: str
    options: Optional[dict] = None

class UrlInput(BaseModel):
    url: HttpUrl
    options: Optional[dict] = None

# Endpoint-specific validators
async def validate_text_request(request: Request, text_input: TextInput, **kwargs):
    """Pre-validator for text conversion"""
    await validate_text_input(
        content=text_input.content.encode('utf-8'),
        metadata={
            "content_type": "text/html",
            "content_length": len(text_input.content)
        }
    )

async def validate_file_request(request: Request, file: UploadFile, **kwargs):
    """Pre-validator for file conversion"""
    return await validate_upload_file(file=file)

async def validate_url_request(response: requests.Response, **kwargs):
    """Validator for URL response"""
    content_type = response.headers.get('content-type', '')
    validate_content_type(content_type)
    validate_file_size(response.content)

def log_conversion_attempt(
    conversion_type: str,
    metadata: Dict[str, Any],
    user_id: Optional[str] = None
) -> None:
    """Log conversion attempt with metadata."""
    log_data = {
        "conversion_type": conversion_type,
        "user_id": user_id,
    }
    
    for key, value in metadata.items():
        if key == 'filename':
            log_data['input_filename'] = value
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
    log_data = {
        "conversion_type": conversion_type,
        "success": success,
        "duration_ms": round(duration * 1000, 2),
    }

    for key, value in metadata.items():
        if key == 'filename':
            log_data['input_filename'] = value
        else:
            log_data[key] = value

    if error:
        log_data["error"] = str(error)
        log_data["error_type"] = error.__class__.__name__

    perf_logger.info(
        f"{conversion_type} conversion completed",
        extra=log_data
    )

    if success:
        logger.info(f"{conversion_type} conversion successful", extra=log_data)
    else:
        logger.error(f"{conversion_type} conversion failed", extra=log_data)

@contextmanager
def save_temp_file(content: bytes, suffix: str) -> str:
    """Save content to a temporary file and return the file path."""
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, mode='w+b', delete=False) as temp_file:
            temp_file_path = temp_file.name
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
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Temporary file removed: {temp_file_path}")
            except Exception as e:
                logger.warning(
                    "Failed to remove temporary file",
                    extra={
                        "path": temp_file_path,
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

    except ConversionError:
        raise
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

@router.post(
    "/convert/text",
    response_class=PlainTextResponse
)
@handle_api_operation(
    "convert_text",
    pre_validators=[validate_text_request],
    error_map={
        FileProcessingError: (status.HTTP_400_BAD_REQUEST, None),
        ConversionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
        RateLimitExceeded: (status.HTTP_429_TOO_MANY_REQUESTS, None),
        **DEFAULT_ERROR_MAP
    }
)
async def convert_text(
    request: Request,
    response: Response,
    text_input: TextInput,
    api_key: APIKey = Depends(get_api_key)
):
    """Convert text or HTML to markdown."""
    # Apply rate limiting
    await rate_limit(
        rate=settings.RATE_LIMITS["/api/v1/convert/text"]["rate"],
        per=settings.RATE_LIMITS["/api/v1/convert/text"]["per"]
    )(request, response)

    log_conversion_attempt(
        "text",
        {
            "content_length": len(text_input.content),
            "has_options": bool(text_input.options)
        },
        str(api_key.id) if api_key else None
    )
    
    with save_temp_file(text_input.content.encode('utf-8'), suffix='.html') as temp_file_path:
        markdown_content = process_conversion(temp_file_path, '.html')
        return PlainTextResponse(content=markdown_content)

@router.post(
    "/convert/file",
    response_class=PlainTextResponse
)
@handle_api_operation(
    "convert_file",
    pre_validators=[validate_file_request],
    error_map={
        ConversionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
        RateLimitExceeded: (status.HTTP_429_TOO_MANY_REQUESTS, None),
        **DEFAULT_ERROR_MAP
    }
)
async def convert_file(
    request: Request,
    response: Response,  # Add response parameter
    file: UploadFile = File(...),
    api_key: APIKey = Depends(get_api_key)
) -> PlainTextResponse:
    """Convert an uploaded file to markdown."""
    # Apply rate limiting
    await rate_limit(
        rate=settings.RATE_LIMITS["/api/v1/convert/file"]["rate"],
        per=settings.RATE_LIMITS["/api/v1/convert/file"]["per"]
    )(request, response)

    ext, content = await validate_upload_file(file=file)
    
    log_conversion_attempt(
        "file",
        {
            "filename": file.filename,
            "content_type": file.content_type,
            "extension": ext,
        },
        str(api_key.id) if api_key else None
    )
    
    with save_temp_file(content, suffix=ext) as temp_file_path:
        markdown_content = process_conversion(
            temp_file_path,
            ext,
            content_type=file.content_type
        )
        
        return PlainTextResponse(
            content=markdown_content,
            status_code=status.HTTP_200_OK
        )

@router.post(
    "/convert/url",
    response_class=PlainTextResponse
)
@handle_api_operation(
    "convert_url",
    error_map={
        requests.ConnectionError: (status.HTTP_502_BAD_GATEWAY, None),
        requests.Timeout: (status.HTTP_502_BAD_GATEWAY, None),
        requests.RequestException: (status.HTTP_502_BAD_GATEWAY, None),
        ContentTypeError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
        ConversionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
        FileProcessingError: (status.HTTP_400_BAD_REQUEST, None),
        RateLimitExceeded: (status.HTTP_429_TOO_MANY_REQUESTS, None),
    }
)
async def convert_url(
    request: Request,
    response: Response,  # Add response parameter
    url_input: UrlInput,
    api_key: APIKey = Depends(get_api_key)
) -> PlainTextResponse:
    """Fetch a URL and convert its content to markdown."""
    # Apply rate limiting
    await rate_limit(
        rate=settings.RATE_LIMITS["/api/v1/convert/url"]["rate"],
        per=settings.RATE_LIMITS["/api/v1/convert/url"]["per"]
    )(request, response)

    log_conversion_attempt(
        "url",
        {
            "url": str(url_input.url),
            "has_options": bool(url_input.options),
        },
        str(api_key.id) if api_key else None
    )

    response = requests.get(
        str(url_input.url),
        headers={
            'User-Agent': settings.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        },
        timeout=settings.REQUEST_TIMEOUT,
        allow_redirects=True
    )
    response.raise_for_status()
    
    await validate_url_request(response)

    with save_temp_file(response.content, suffix='.html') as temp_file_path:
        markdown_content = process_conversion(
            temp_file_path,
            '.html',
            url=str(url_input.url)
        )
        
        return PlainTextResponse(
            content=markdown_content,
            status_code=status.HTTP_200_OK
        )
