from functools import wraps
from typing import Callable, Type, Optional, Dict, Tuple
from fastapi import HTTPException, status
import requests
import logging
from app.utils.audit import audit_log
import time
from app.core.errors.base import OperationError
from app.core.errors.exceptions import FileProcessingError, ConversionError

logger = logging.getLogger(__name__)

# Define standard error mappings
DEFAULT_ERROR_MAP = {
    FileProcessingError: (status.HTTP_400_BAD_REQUEST, None),
    requests.ConnectionError: (status.HTTP_502_BAD_GATEWAY, None),
    requests.Timeout: (status.HTTP_502_BAD_GATEWAY, None),
    requests.RequestException: (status.HTTP_502_BAD_GATEWAY, None),
    ConversionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
    OperationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
    Exception: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
}

def handle_api_operation(
    operation_name: str,
    error_map: Optional[Dict[Type[Exception], Tuple[int, Optional[str]]]] = None,
    audit: bool = True
):
    """
    Decorator for handling API operation errors consistently.
    
    Args:
        operation_name: Name of the operation for logging
        error_map: Mapping of exception types to (status_code, message)
                  Use None as message to pass through the original error message
        audit: Whether to create audit logs
    """
    # Combine default error map with provided error map
    final_error_map = DEFAULT_ERROR_MAP.copy()
    if error_map:
        final_error_map.update(error_map)

    def decorator(func: Callable):
        # Get logger for the module where decorator is used
        logger = logging.getLogger(func.__module__)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                # Get user_id from kwargs if available (api_key dependency)
                api_key = kwargs.get('api_key', {})
                user_id = getattr(api_key, 'id', None)
                
                # Log operation start
                logger.info(f"Starting {operation_name}")
                
                # Execute operation
                result = await func(*args, **kwargs)
                
                # Calculate duration
                duration = time.time() - start_time
                
                # Log success
                logger.info(
                    f"Completed {operation_name}",
                    extra={"duration": duration}
                )
                
                # Audit successful operation
                if audit:
                    audit_log(
                        action=operation_name,
                        user_id=user_id,
                        details={
                            "duration": duration,
                            "status": "success"
                        }
                    )
                
                return result
                
            except Exception as e:
                # Handle all exceptions uniformly
                duration = time.time() - start_time

                # Special handling for responses library exceptions
                if hasattr(e, 'body') and isinstance(e.body, Exception):
                    actual_exception = e.body
                    error_type = type(actual_exception)
                else:
                    actual_exception = e
                    error_type = type(e)
                
                # Find most specific error mapping
                error_config = None
                for exc_type, config in final_error_map.items():
                    if isinstance(actual_exception, exc_type):
                        error_config = config
                        break
                
                if error_config:
                    status_code, message = error_config
                    # Use original error message if message is None
                    detail = str(actual_exception) if message is None else message
                else:
                    status_code = getattr(actual_exception, 'status_code', 500)
                    detail = str(actual_exception)

                # Log at appropriate level
                if status_code >= 500:
                    logger.exception(
                        f"{operation_name} failed",
                        extra={
                            "duration": duration,
                            "error_type": error_type.__name__,
                            "error_message": str(actual_exception),
                            "status_code": status_code
                        }
                    )
                else:
                    logger.warning(
                        f"{operation_name} error",
                        extra={
                            "duration": duration,
                            "error_type": error_type.__name__,
                            "error_message": str(actual_exception),
                            "status_code": status_code
                        }
                    )
                
                # Audit error
                if audit:
                    audit_log(
                        action=operation_name,
                        user_id=user_id,
                        details={
                            "error": str(actual_exception),
                            "error_type": error_type.__name__,
                            "duration": duration,
                            "status_code": status_code
                        },
                        status="failure"
                    )
                
                # Raise HTTP exception with appropriate status and detail
                raise HTTPException(
                    status_code=status_code,
                    detail=detail
                )
                
        return wrapper
    return decorator

__all__ = ["handle_api_operation", "OperationError", "DEFAULT_ERROR_MAP"]