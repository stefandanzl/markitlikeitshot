# app/core/error_handlers.py

from functools import wraps
from typing import Callable, Type, Optional, Dict, Tuple
from fastapi import HTTPException, status
import requests
import logging
from app.utils.audit import audit_log
import time

logger = logging.getLogger(__name__)

class OperationError(Exception):
    """Base class for operation errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

def handle_api_operation(
    operation_name: str,
    error_map: Dict[Type[Exception], Tuple[int, str]] = None,
    audit: bool = True
):
    """
    Decorator for handling API operation errors consistently.
    
    Args:
        operation_name: Name of the operation for logging
        error_map: Mapping of exception types to (status_code, message)
        audit: Whether to create audit logs
    """
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
                
            except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
                # Special handling for URL-related errors to prevent double logging
                duration = time.time() - start_time
                error_config = error_map.get(type(e)) if error_map else None
                status_code = error_config[0] if error_config else 400
                message = error_config[1] if error_config else "URL request failed"
                
                logger.warning(
                    f"{operation_name} URL error",
                    extra={
                        "duration": duration,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                
                if audit:
                    audit_log(
                        action=operation_name,
                        user_id=user_id,
                        details={
                            "error": str(e),
                            "duration": duration
                        },
                        status="failure"
                    )
                
                raise HTTPException(
                    status_code=status_code,
                    detail=message
                )
                
            except Exception as e:
                # Handle all other exceptions
                duration = time.time() - start_time
                error_config = error_map.get(type(e)) if error_map else None
                status_code = error_config[0] if error_config else 500
                message = error_config[1] if error_config else str(e)
                
                logger.exception(
                    f"{operation_name} failed",
                    extra={
                        "duration": duration,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                
                if audit:
                    audit_log(
                        action=operation_name,
                        user_id=user_id,
                        details={
                            "error": str(e),
                            "duration": duration
                        },
                        status="failure"
                    )
                
                raise HTTPException(
                    status_code=status_code,
                    detail=message
                )
                
        return wrapper
    return decorator

def handle_url_operation(operation_name: str):
    """Decorator for handling URL-related operation errors."""
    return handle_api_operation(
        operation_name=operation_name,
        error_map={
            requests.exceptions.ConnectionError: (status.HTTP_400_BAD_REQUEST, "Unable to connect to the specified URL"),
            requests.exceptions.RequestException: (status.HTTP_400_BAD_REQUEST, "Failed to fetch URL content")
        }
    )