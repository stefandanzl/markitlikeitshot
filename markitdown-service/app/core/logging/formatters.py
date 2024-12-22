import logging
import json
from datetime import datetime, UTC

class AuditFormatter(logging.Formatter):
    """Custom formatter for audit logs"""
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
            "environment": record.__dict__.get("environment", "unknown")
        })
        
        return json.dumps(audit_dict, default=str)

__all__ = ["AuditFormatter"]