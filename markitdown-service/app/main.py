from fastapi import FastAPI, UploadFile, File, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional
from markitdown import MarkItDown
from bs4 import BeautifulSoup
import tempfile
import os
import logging
import requests
import re
from app.core.config import settings
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Custom exceptions
class FileProcessingError(Exception):
    pass

class ConversionError(Exception):
    pass

class URLFetchError(Exception):
    pass

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS with settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)

class TextInput(BaseModel):
    content: str
    options: Optional[dict] = None

class UrlInput(BaseModel):
    url: HttpUrl
    options: Optional[dict] = None

def save_temp_file(content: bytes, suffix: str) -> str:
    """
    Save content to a temporary file and return the file path.
    """
    if len(content) > settings.MAX_FILE_SIZE:
        raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        try:
            temp_file.write(content)
            logger.debug(f"Temporary file created at: {temp_file.name}")
            return temp_file.name
        except Exception as e:
            logger.exception("Failed to create temporary file")
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise FileProcessingError(f"Failed to create temporary file: {str(e)}")

def process_conversion(file_path: str, ext: str, url: Optional[str] = None, content_type: str = None) -> str:
    """
    Process conversion using MarkItDown and clean the markdown content.
    """
    try:
        converter = MarkItDown()
        
        if url and "wikipedia.org" in url:
            logger.debug("Using WikipediaConverter for Wikipedia URL")
            result = converter.convert(file_path, file_extension=ext, url=url, converter_type='wikipedia')
        else:
            result = converter.convert(file_path, file_extension=ext, url=url)
            
        markdown_content = result.text_content
        logger.debug("Markdown content cleaned up")
        return markdown_content
    except Exception as e:
        logger.exception("Conversion failed")
        raise ConversionError(f"Failed to convert content: {str(e)}")

@app.post("/convert/text", response_class=PlainTextResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/hour")
async def convert_text(request: Request, text_input: TextInput):
    """Convert text or HTML to markdown."""
    temp_file_path = None
    try:
        logger.debug(f"Received content: {text_input.content[:100]}...")
        content = text_input.content
        temp_file_path = save_temp_file(content.encode('utf-8'), suffix='.html')
        markdown_content = process_conversion(temp_file_path, '.html')
        return markdown_content
    except FileProcessingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during text conversion")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="An unexpected error occurred during conversion")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")

@app.post("/convert/file", response_class=PlainTextResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/hour")
async def convert_file(request: Request, file: UploadFile = File(...)):
    """Convert an uploaded file to markdown."""
    temp_file_path = None
    try:
        _, ext = os.path.splitext(file.filename)
        if ext.lower() not in settings.SUPPORTED_EXTENSIONS:
            raise FileProcessingError(f"Unsupported file type: {ext}")

        content = await file.read()
        if len(content) > settings.MAX_FILE_SIZE:
            raise FileProcessingError(f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE} bytes")

        temp_file_path = save_temp_file(content, suffix=ext)
        markdown_content = process_conversion(temp_file_path, ext)
        return markdown_content
    except FileProcessingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ConversionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error during file conversion")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="An unexpected error occurred during conversion")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")

@app.post("/convert/url", response_class=PlainTextResponse)
@limiter.limit(f"{settings.RATE_LIMIT_REQUESTS}/hour")
async def convert_url(request: Request, url_input: UrlInput):
    """Fetch a URL and convert its content to markdown."""
    temp_file_path = None
    try:
        logger.debug(f"Fetching URL: {url_input.url}")
        headers = {'User-Agent': settings.USER_AGENT}
        
        response = requests.get(
            str(url_input.url), 
            headers=headers, 
            timeout=settings.REQUEST_TIMEOUT
        )
        response.raise_for_status()
        
        content = response.content
        temp_file_path = save_temp_file(content, suffix='.html')
        markdown_content = process_conversion(
            temp_file_path,
            '.html',
            url=str(url_input.url)
        )
        return markdown_content
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
        logger.exception("Unexpected error during URL conversion")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="An unexpected error occurred during conversion")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug("Temporary file cleaned up")