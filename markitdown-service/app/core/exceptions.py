from fastapi import status
from app.core.base_exceptions import OperationError

class FileProcessingError(OperationError):
    """Raised when file processing fails"""
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_400_BAD_REQUEST)

class ConversionError(OperationError):
    """Raised when conversion fails"""
    def __init__(self, message: str):
        super().__init__(message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

class ContentTypeError(ConversionError):
    """Raised when content type is not supported"""
    def __init__(self, content_type: str):
        super().__init__(f"Unsupported content type: {content_type}")

__all__ = ["FileProcessingError", "ConversionError", "ContentTypeError"]