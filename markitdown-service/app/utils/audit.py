import logging
from datetime import datetime, UTC
from typing import Optional, Any, Dict, Union
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from app.core.config.settings import settings
from app.core.logging.formatters import AuditFormatter

# Create the logs directory if it doesn't exist
Path(settings.LOG_DIR).mkdir(exist_ok=True)

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)  # Audit logs should always be at INFO level

if settings.AUDIT_LOG_ENABLED and not audit_logger.handlers:
    # Create audit log handler with rotation
    audit_handler = TimedRotatingFileHandler(
        filename=settings.AUDIT_LOG_FILE,
        when='midnight',
        interval=1,
        backupCount=settings.AUDIT_LOG_RETENTION_DAYS,
        encoding=settings.LOG_ENCODING
    )
    
    # Use the centralized AuditFormatter
    formatter = AuditFormatter()
    audit_handler.setFormatter(formatter)
    audit_logger.addHandler(audit_handler)

    # Prevent audit logs from propagating to root logger
    audit_logger.propagate = False

def audit_log(
    action: str,
    user_id: Optional[str],
    details: Union[str, Dict[str, Any]],
    status: str = "success",
    **extra: Any
) -> None:
    """
    Log an audit event with enhanced context and formatting.
    
    Args:
        action: The action being audited
        user_id: The ID of the user performing the action (if applicable)
        details: Additional details about the action (string or dict)
        status: The status of the action ("success" or "failure")
        **extra: Additional key-value pairs to include in the audit log
    """
    if not settings.AUDIT_LOG_ENABLED:
        return

    try:
        # Create the audit log entry
        audit_entry = {
            "action": action,
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION
        }

        # Handle details based on type
        if isinstance(details, dict):
            audit_entry["details"] = details
        else:
            audit_entry["details"] = {"message": str(details)}

        # Add any extra fields
        if extra:
            audit_entry["extra"] = extra

        # Add environment context
        audit_entry["context"] = {
            "environment": settings.ENVIRONMENT,
            "version": settings.VERSION,
            "component": "audit"
        }

        # Log at appropriate level based on status
        log_level = logging.WARNING if status == "failure" else logging.INFO
        
        audit_logger.log(
            level=log_level,
            msg=audit_entry
        )

    except Exception as e:
        # Fallback logging in case of errors
        fallback_logger = logging.getLogger("app.utils.audit")
        fallback_logger.error(
            "Failed to create audit log",
            exc_info=True,
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__,
                "action": action,
                "user_id": user_id,
                "status": status,
                "timestamp": datetime.now(UTC).isoformat()
            }
        )

__all__ = ["audit_log"]