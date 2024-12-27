# app/core/errors/handlers.py
from functools import wraps
from typing import Callable, Type, Optional, Dict, Tuple, List
from fastapi import HTTPException, status, Request
import requests
import logging
from app.core.audit import audit_log, AuditAction
import time
from app.core.errors.base import OperationError
from app.core.errors.exceptions import FileProcessingError, ConversionError
from app.core.rate_limiting.limiter import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError
import inspect
import traceback

logger = logging.getLogger(__name__)

# Define standard error mappings
DEFAULT_ERROR_MAP = {
    FileProcessingError: (status.HTTP_400_BAD_REQUEST, None),
    requests.ConnectionError: (status.HTTP_502_BAD_GATEWAY, None),
    requests.Timeout: (status.HTTP_502_BAD_GATEWAY, None),
    requests.RequestException: (status.HTTP_502_BAD_GATEWAY, None),
    ConversionError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
    OperationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, None),
    RateLimitExceeded: (status.HTTP_429_TOO_MANY_REQUESTS, None),
    SQLAlchemyError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error occurred"),
    Exception: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
}

# Map operations to AuditActions
OPERATION_TO_AUDIT_ACTION = {
    "convert_text": AuditAction.CONVERT_TEXT,
    "convert_file": AuditAction.CONVERT_FILE,
    "convert_url": AuditAction.CONVERT_URL,
}

def get_error_config(exception: Exception, error_map: Dict[Type[Exception], Tuple[int, Optional[str]]]) -> Tuple[Tuple[int, Optional[str]], Exception]:
    """
    Get error configuration for an exception.
    
    Args:
        exception: The exception to get configuration for
        error_map: Mapping of exception types to (status_code, message)
    
    Returns:
        Tuple containing ((status_code, message), actual_exception)
    """
    # Handle responses library exceptions
    if hasattr(exception, 'body') and isinstance(exception.body, Exception):
        actual_exception = exception.body
    else:
        actual_exception = exception

    # Find most specific error mapping
    for exc_type, config in error_map.items():
        if isinstance(actual_exception, exc_type):
            return config, actual_exception
    
    # Default error handling
    status_code = getattr(actual_exception, 'status_code', 500)
    return (status_code, str(actual_exception)), actual_exception

def get_validator_parameters(validator: Callable) -> set:
    """Get the parameter names for a validator function."""
    return {
        param.name for param in inspect.signature(validator).parameters.values()
        if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
    }

async def run_validators(
    validators: List[Callable],
    args: tuple,
    kwargs: dict,
    context: Optional[dict] = None
) -> None:
    """
    Run a list of validators with given arguments.
    
    Args:
        validators: List of validator functions to run
        args: Positional arguments to pass to validators
        kwargs: Keyword arguments to pass to validators
        context: Optional context dictionary to pass to validators
    """
    if not validators:
        return

    for validator in validators:
        # Get the parameters this validator accepts
        valid_params = get_validator_parameters(validator)
        
        # Build validator kwargs with only the parameters it accepts
        validator_kwargs = {
            k: v for k, v in kwargs.items()
            if k in valid_params
        }
        
        # Add context if the validator accepts it
        if context and 'context' in valid_params:
            validator_kwargs['context'] = context.copy()
        
        # Find request object in args or kwargs if validator needs it
        if 'request' in valid_params:
            request = next(
                (arg for arg in args if isinstance(arg, Request)),
                kwargs.get('request')
            )
            if request:
                validator_kwargs['request'] = request
        
        await validator(**validator_kwargs)

def handle_api_operation(
    operation_name: str,
    pre_validators: Optional[List[Callable]] = None,
    post_validators: Optional[List[Callable]] = None,
    error_map: Optional[Dict[Type[Exception], Tuple[int, Optional[str]]]] = None,
    audit: bool = True
):
    """
    Enhanced decorator for handling API operation errors consistently.
    
    Args:
        operation_name: Name of the operation for logging
        pre_validators: List of validation functions to run before main operation
        post_validators: List of validation functions to run after main operation
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
            api_key = kwargs.get('api_key', {})
            user_id = getattr(api_key, 'id', None)
            
            try:
                # Create validation context
                validation_context = {
                    'operation_name': operation_name,
                    'user_id': user_id,
                    'start_time': start_time
                }
                
                # Run pre-operation validators
                await run_validators(pre_validators, args, kwargs, validation_context)
                
                # Log operation start
                logger.info(f"Starting {operation_name}")
                
                # Execute operation
                result = await func(*args, **kwargs)
                
                # Run post-operation validators
                if post_validators:
                    validation_context['result'] = result
                    await run_validators(post_validators, args, kwargs, validation_context)
                
                # Calculate duration and log success
                duration = time.time() - start_time
                logger.info(f"Completed {operation_name}", extra={"duration": duration})
                
                # Audit successful operation
                if audit:
                    audit_action = OPERATION_TO_AUDIT_ACTION.get(operation_name, operation_name)
                    audit_log(
                        action=audit_action,
                        user_id=user_id,
                        details={"duration": duration, "status": "success"}
                    )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                (status_code, message), actual_exception = get_error_config(e, final_error_map)
                
                # Use original error message if message is None
                detail = str(actual_exception) if message is None else message
                
                # Log at appropriate level with consistent format
                log_data = {
                    "duration": duration,
                    "error_type": actual_exception.__class__.__name__,
                    "error_message": str(actual_exception),
                    "status_code": status_code,
                    "operation": operation_name,
                    "user_id": user_id,
                }
                
                if status_code >= 500:
                    log_data["traceback"] = traceback.format_exc()
                    logger.exception(f"{operation_name} failed", extra=log_data)
                else:
                    logger.warning(f"{operation_name} error", extra=log_data)
                
                # Audit error with consistent format
                if audit:
                    audit_action = OPERATION_TO_AUDIT_ACTION.get(operation_name, operation_name)
                    audit_log(
                        action=audit_action,
                        user_id=user_id,
                        details={**log_data, "error": str(actual_exception)},
                        status="failure"
                    )
                
                # Ensure we always return a proper HTTP response
                if isinstance(actual_exception, HTTPException):
                    raise actual_exception
                else:
                    raise HTTPException(status_code=status_code, detail=detail)
                
        return wrapper
    return decorator

__all__ = [
    "handle_api_operation",
    "OperationError",
    "DEFAULT_ERROR_MAP",
    "run_validators"
]
