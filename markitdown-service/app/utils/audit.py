import logging
import json
from datetime import datetime, UTC
from typing import Optional, Any, Dict, Union
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

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
    
    # Create custom formatter for audit logs
    class AuditFormatter(logging.Formatter):
        def format(self, record):
            if isinstance(record.msg, dict):
                # If msg is already a dict, use it directly
                audit_dict = record.msg
            else:
                # Convert message to dict format
                audit_dict = {
                    "message": record.msg,
                    "extra": record.__dict__.get("extra", {})
                }
            
            # Add standard audit fields
            audit_dict.update({
                "timestamp": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "environment": settings.ENVIRONMENT
            })
            
            return json.dumps(audit_dict, default=str)

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

def get_audit_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    action_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get statistics about audit logs within a specified time range.
    
    Args:
        start_date: Start date for the statistics (optional)
        end_date: End date for the statistics (optional)
        action_type: Filter by specific action type (optional)
    
    Returns:
        Dictionary containing audit statistics
    """
    try:
        # This is a placeholder for actual implementation
        # In a real implementation, you would parse the audit log file
        # and generate statistics
        stats = {
            "total_events": 0,
            "success_count": 0,
            "failure_count": 0,
            "action_counts": {},
            "time_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            },
            "generated_at": datetime.now(UTC).isoformat()
        }
        
        return stats

    except Exception as e:
        logger = logging.getLogger("app.utils.audit")
        logger.error(
            "Failed to generate audit statistics",
            exc_info=True,
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "action_type": action_type
            }
        )
        return {
            "error": "Failed to generate audit statistics",
            "details": str(e),
            "timestamp": datetime.now(UTC).isoformat()
        }

def cleanup_audit_logs() -> bool:
    """
    Clean up old audit logs based on retention policy.
    
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    try:
        # The TimedRotatingFileHandler handles log rotation and cleanup
        # This method is provided for manual cleanup if needed
        return True
    except Exception as e:
        logger = logging.getLogger("app.utils.audit")
        logger.error(
            "Failed to clean up audit logs",
            exc_info=True,
            extra={
                "error": str(e),
                "error_type": e.__class__.__name__,
                "timestamp": datetime.now(UTC).isoformat()
            }
        )
        return False

__all__ = ["audit_log", "get_audit_stats", "cleanup_audit_logs"]