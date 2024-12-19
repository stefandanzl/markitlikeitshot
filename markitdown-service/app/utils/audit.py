import logging
from datetime import datetime
from typing import Optional
from app.core.config import settings

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

if settings.AUDIT_LOG_ENABLED:
    handler = logging.FileHandler(settings.AUDIT_LOG_FILE)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)

def audit_log(
    action: str,
    user_id: Optional[str],
    details: str,
    status: str = "success"
) -> None:
    """Log an audit event."""
    if settings.AUDIT_LOG_ENABLED:
        audit_logger.info(
            f"Action: {action} | User: {user_id} | "
            f"Status: {status} | Details: {details}"
        )