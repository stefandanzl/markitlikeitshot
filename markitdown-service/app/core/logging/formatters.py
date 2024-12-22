import logging
import json
from datetime import datetime, UTC
from app.core.config import settings

class AuditFormatter(logging.Formatter):
    """
    Custom formatter for audit logs that converts log records to structured JSON.
    Produces concise, non-redundant audit logs with essential fields.
    """
    def format(self, record):
        # Base audit fields
        audit_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "environment": settings.ENVIRONMENT,
            "component": "audit"
        }

        # Handle message based on type
        if isinstance(record.msg, dict):
            # Extract core fields from msg dict
            msg_dict = record.msg
            audit_dict.update({
                "action": msg_dict.get("action"),
                "user_id": msg_dict.get("user_id"),
                "status": msg_dict.get("status", "success"),
                "service": msg_dict.get("service", settings.PROJECT_NAME),
            })
            
            # Add details if present
            if "details" in msg_dict:
                audit_dict["details"] = msg_dict["details"]
            
            # Add extra fields if present
            if "extra" in msg_dict:
                audit_dict["extra"] = msg_dict["extra"]
        else:
            # Simple string message
            audit_dict.update({
                "message": str(record.msg),
                "extra": getattr(record, "extra", {})
            })

        # Add minimal execution context
        audit_dict["context"] = {
            "thread": record.thread,
            "thread_name": record.threadName
        }

        return json.dumps(audit_dict, default=str)

__all__ = ["AuditFormatter"]