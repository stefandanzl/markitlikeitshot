from enum import Enum

class AuditAction(str, Enum):
    # API Key Actions
    API_KEY_USED = "api_key_used"
    API_KEY_CREATED = "api_key_created"
    API_KEY_DEACTIVATED = "api_key_deactivated"
    API_KEY_REACTIVATED = "api_key_reactivated"
    API_KEY_INVALID = "api_key_invalid"
    ADMIN_ACCESS_DENIED = "admin_access_denied"
    
    # User Actions
    USER_CREATED = "create_user"
    USER_STATUS_UPDATED = "update_user_status"
    
    # Service Actions
    SERVICE_STARTUP = "service_startup"
    SERVICE_SHUTDOWN = "service_shutdown"
    HEALTH_CHECK = "health_check"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    
    # Conversion Actions
    CONVERT_TEXT = "convert_text"
    CONVERT_FILE = "convert_file"
    CONVERT_URL = "convert_url"

__all__ = ["AuditAction"]