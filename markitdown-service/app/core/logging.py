# app/core/logging.py (new file)

from typing import Dict, Any
from pathlib import Path
from app.core.config import settings

def get_base_logging_config() -> Dict[str, Any]:
    """Base logging configuration with common settings."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": settings.LOG_FORMAT,
                "datefmt": settings.LOG_DATE_FORMAT
            },
            "simple": {
                "format": "%(message)s"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "level": settings.get_log_level
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "formatter": "detailed",
                "filename": f"{settings.LOG_DIR}/app_{settings.ENVIRONMENT}.log",
                "when": settings.LOG_ROTATION,
                "backupCount": settings.LOG_BACKUP_COUNT,
                "encoding": settings.LOG_ENCODING
            },
            "null": {
                "class": "logging.NullHandler"
            }
        },
        "loggers": {
            "app": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False
            },
            "sqlalchemy": {
                "handlers": ["file"],
                "level": "INFO",
                "propagate": False
            }
        }
    }

def get_web_logging_config() -> Dict[str, Any]:
    """Web service specific logging configuration."""
    config = get_base_logging_config()
    
    # Add web-specific formatters
    config["formatters"]["worker"] = {
        "format": "worker[%(process)d] - %(message)s"
    }
    
    # Configure handlers based on environment
    if settings.ENVIRONMENT == "test":
        # In test environment, only log errors and use simple format
        config["formatters"]["test"] = {
            "format": "%(levelname)s: %(message)s"
        }
        config["handlers"]["console"].update({
            "formatter": "test",
            "level": "ERROR"  # Only show ERROR and above in tests
        })
        # Disable file logging in test environment
        config["handlers"]["file"] = {
            "class": "logging.NullHandler"
        }
    
    # Add web-specific loggers
    config["loggers"].update({
        "uvicorn": {
            "handlers": ["console"],
            "level": "WARNING" if settings.ENVIRONMENT == "test" else "INFO",
            "propagate": False
        },
        "uvicorn.error": {
            "handlers": ["console"],
            "level": "WARNING" if settings.ENVIRONMENT == "test" else "INFO",
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["null"],
            "level": "WARNING",
            "propagate": False
        },
        # Configure app loggers
        "app": {
            "handlers": ["console", "file"],
            "level": "ERROR" if settings.ENVIRONMENT == "test" else "DEBUG",
            "propagate": False
        },
        "app.api": {
            "handlers": ["console", "file"],
            "level": "ERROR" if settings.ENVIRONMENT == "test" else "DEBUG",
            "propagate": False
        }
    })
    
    return config

def get_cli_logging_config(quiet: bool = False) -> Dict[str, Any]:
    """CLI specific logging configuration."""
    config = get_base_logging_config()
    
    # Modify console formatter for CLI
    config["formatters"]["cli"] = {
        "format": "%(levelname)s: %(message)s" if not quiet else "%(message)s"
    }
    
    # Add CLI specific handlers
    log_dir = Path(settings.LOG_DIR)
    cli_log_file = log_dir / f"cli_{settings.ENVIRONMENT}.log"
    sql_log_file = log_dir / f"sql_{settings.ENVIRONMENT}.log"
    
    config["handlers"].update({
        "cli_file": {
            "class": "logging.FileHandler",
            "filename": str(cli_log_file),
            "formatter": "detailed",
            "level": "DEBUG"
        },
        "sql_file": {
            "class": "logging.FileHandler",
            "filename": str(sql_log_file),
            "formatter": "detailed",
            "level": "DEBUG"
        }
    })
    
    # Update loggers for CLI
    config["loggers"].update({
        "app.cli": {
            "handlers": ["console", "cli_file"],
            "level": "DEBUG",
            "propagate": False
        }
    })
    
    return config

