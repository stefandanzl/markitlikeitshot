# app/core/validation/validators.py
import os
from typing import Optional, Tuple, Dict, Any
from fastapi import UploadFile, Request
from app.core.errors.exceptions import FileProcessingError, ContentTypeError
from app.core.config.settings import settings
import logging

logger = logging.getLogger(__name__)

def validate_file_size(content: bytes, max_size: int = None) -> None:
    """
    Validate file size against configured limits.
    
    Args:
        content: The file content in bytes
        max_size: Optional custom max size, defaults to settings.MAX_FILE_SIZE
    
    Raises:
        FileProcessingError: If file size exceeds limit
    """
    max_size = max_size or settings.MAX_FILE_SIZE
    content_size = len(content)
    
    if content_size > max_size:
        logger.warning(
            "File size validation failed",
            extra={
                "size": content_size,
                "limit": max_size,
                "exceeded_by": content_size - max_size
            }
        )
        raise FileProcessingError(
            f"File size ({content_size} bytes) exceeds maximum limit of {max_size} bytes"
        )

def validate_file_extension(filename: str, allowed_extensions: Optional[set] = None) -> str:
    """
    Validate file extension against supported types.
    
    Args:
        filename: Name of the file to validate
        allowed_extensions: Optional set of allowed extensions, defaults to settings.SUPPORTED_EXTENSIONS
    
    Returns:
        str: The validated extension in lowercase
    
    Raises:
        FileProcessingError: If file extension is not supported
    """
    allowed_extensions = allowed_extensions or set(settings.SUPPORTED_EXTENSIONS)
    _, ext = os.path.splitext(filename)
    ext_lower = ext.lower()
    
    if not ext_lower:
        logger.warning("No file extension found", extra={"input_filename": filename})
        raise FileProcessingError("No file extension provided")
    
    if ext_lower not in allowed_extensions:
        logger.warning(
            "Unsupported file extension",
            extra={
                "extension": ext_lower,
                "supported_extensions": list(allowed_extensions)
            }
        )
        raise FileProcessingError(
            f"Unsupported file type: {ext}. Supported types: {', '.join(allowed_extensions)}"
        )
    
    return ext_lower

def validate_content_type(
    content_type: str,
    allowed_types: Tuple[str, ...] = ('text/html', 'application/xhtml+xml')
) -> None:
    """
    Validate content type against allowed types.
    
    Args:
        content_type: The content type to validate
        allowed_types: Tuple of allowed content type prefixes
    
    Raises:
        ContentTypeError: If content type is not supported
    """
    if not content_type:
        logger.warning("No content type provided")
        raise ContentTypeError("No content type provided")
    
    # Strip parameters from content type (e.g., 'text/html; charset=utf-8' -> 'text/html')
    base_content_type = content_type.split(';')[0].strip()
    
    if not any(base_content_type.startswith(allowed) for allowed in allowed_types):
        logger.warning(
            "Unsupported content type",
            extra={
                "content_type": base_content_type,
                "allowed_types": allowed_types
            }
        )
        raise ContentTypeError(
            f"Unsupported content type: {base_content_type}. "
            f"Supported types: {', '.join(allowed_types)}"
        )

def validate_file_content(
    content: bytes,
    metadata: Dict[str, Any]
) -> None:
    """
    Validate file content exists and is not empty.
    
    Args:
        content: The file content in bytes
        metadata: Dictionary containing file metadata for logging
    
    Raises:
        FileProcessingError: If content is empty or invalid
    """
    if not content:
        # Rename 'filename' to 'input_filename' in metadata for logging
        log_metadata = metadata.copy()
        if 'filename' in log_metadata:
            log_metadata['input_filename'] = log_metadata.pop('filename')
        logger.warning(
            "Empty file content",
            extra=log_metadata
        )
        raise FileProcessingError("Empty file provided")

async def validate_upload_file(request: Optional[Request] = None, file: Optional[UploadFile] = None, **kwargs) -> Tuple[str, bytes]:
    """
    Validate an uploaded file, checking extension and content.
    
    Args:
        request: Optional FastAPI Request object
        file: FastAPI UploadFile object
        **kwargs: Additional keyword arguments (ignored)
    
    Returns:
        Tuple[str, bytes]: Validated extension and file content
    
    Raises:
        FileProcessingError: If validation fails
    """
    if not file:
        raise FileProcessingError("No file provided")

    # Validate extension first (quick check before reading content)
    ext = validate_file_extension(file.filename)
    
    # Read and validate content
    content = await file.read()
    await file.seek(0)  # Reset file position for subsequent reads
    
    metadata = {
        "filename": file.filename,
        "content_type": file.content_type,
        "extension": ext,
        "size": len(content)
    }
    
    validate_file_content(content, metadata)
    validate_file_size(content)
    
    return ext, content

async def validate_text_input(request: Optional[Request] = None, content: bytes = None, **kwargs) -> None:
    """
    Validate text input content.
    
    Args:
        request: Optional FastAPI Request object
        content: Text content in bytes
        **kwargs: Additional keyword arguments (ignored)
    
    Raises:
        FileProcessingError: If validation fails
    """
    if not content:
        raise FileProcessingError("No content provided")
        
    metadata = {
        "content_type": "text/plain",
        "size": len(content)
    }
    
    validate_file_content(content, metadata)
    validate_file_size(content)

__all__ = [
    "validate_file_size",
    "validate_file_extension",
    "validate_content_type",
    "validate_file_content",
    "validate_upload_file",
    "validate_text_input"
]
