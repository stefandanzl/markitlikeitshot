from typing import Dict, Any
from pathlib import Path
import logging
import logging.handlers
import fcntl
import gzip
import shutil
import os
from datetime import datetime
from app.core.config.settings import settings
from app.core.logging.formatters import AuditFormatter

logger = logging.getLogger(__name__)

class SafeRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    """Thread and process-safe rotating file handler with compression."""
    
    def __init__(self, filename: str, **kwargs):
        # Ensure log directory exists with proper permissions
        log_dir = os.path.dirname(filename)
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file if it doesn't exist
        if not os.path.exists(filename):
            Path(filename).touch()
            os.chmod(filename, 0o644)
        
        super().__init__(filename, **kwargs)
        self.rotator = self._rotator
        self.namer = self._namer
        
    def _namer(self, default_name: str) -> str:
        """Generate the name of the rotated file."""
        # Extract the base name without the path
        base_name = Path(default_name).stem
        # Add date suffix in our standard format
        date_suffix = datetime.now().strftime('%Y%m%d')
        return f"{base_name}-{date_suffix}.log"
    
    def _rotator(self, source: str, dest: str) -> None:
        """Custom rotator that adds file locking and compression."""
        try:
            # Ensure directory exists with proper permissions
            dest_dir = os.path.dirname(dest)
            os.makedirs(dest_dir, exist_ok=True)
            
            with open(source, 'a') as f:
                try:
                    # Acquire exclusive lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    
                    # Copy content and truncate source
                    with open(source, 'rb') as sf:
                        content = sf.read()
                    
                    # Write to new file with proper permissions
                    with open(dest, 'wb') as df:
                        os.chmod(dest, 0o644)  # Set permissions before writing
                        df.write(content)
                    
                    # Truncate source file
                    with open(source, 'w') as sf:
                        pass
                    
                    # Compress the rotated file
                    with open(dest, 'rb') as f_in:
                        gz_path = f"{dest}.gz"
                        with gzip.open(gz_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                        os.chmod(gz_path, 0o644)  # Set permissions for compressed file
                    
                    # Remove the uncompressed rotated file
                    Path(dest).unlink()
                    
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (IOError, OSError) as e:
            logger.error(f"Error rotating log file {source} to {dest}: {str(e)}")
            # Ensure we don't leave partial files
            try:
                if os.path.exists(dest):
                    os.unlink(dest)
                gz_path = f"{dest}.gz"
                if os.path.exists(gz_path):
                    os.unlink(gz_path)
            except OSError as cleanup_error:
                logger.error(f"Error cleaning up after failed rotation: {str(cleanup_error)}")

def get_file_handler(filename: str, formatter: str = "detailed") -> Dict[str, Any]:
    """Get a safe rotating file handler configuration."""
    return {
        "class": "app.core.logging.config.SafeRotatingFileHandler",
        "formatter": formatter,
        "filename": filename,
        "when": settings.LOG_ROTATION,
        "interval": 1,
        "backupCount": settings.LOG_BACKUP_COUNT,
        "encoding": settings.LOG_ENCODING,
        "delay": False,
        "utc": True
    }

def get_base_logging_config() -> Dict[str, Any]:
    """Base logging configuration with common settings."""
    # Ensure log directory exists
    Path(settings.LOG_DIR).mkdir(parents=True, exist_ok=True)
    
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
            },
            "sql": {
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
            "file": get_file_handler(
                f"{settings.LOG_DIR}/app_{settings.ENVIRONMENT}.log",
                "detailed"
            ),
            "sql_file": get_file_handler(
                f"{settings.LOG_DIR}/sql_{settings.ENVIRONMENT}.log",
                "sql"
            ),
            "null": {
                "class": "logging.NullHandler"
            }
        },
        "loggers": {
            "app": {
                "handlers": ["console", "file"],
                "level": settings.get_log_level,
                "propagate": False
            },
            "sqlalchemy.engine": {
                "handlers": ["sql_file"],
                "level": settings.get_component_log_level("sqlalchemy.engine"),
                "propagate": False
            },
            "sqlalchemy.pool": {
                "handlers": ["sql_file"],
                "level": settings.get_component_log_level("sqlalchemy.pool"),
                "propagate": False
            },
            "sqlalchemy.dialects": {
                "handlers": ["sql_file"],
                "level": settings.get_component_log_level("sqlalchemy.dialects"),
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
            "level": "ERROR"  # Show ERROR and above in tests
        })
        # Disable file logging in test environment
        config["handlers"]["file"] = {
            "class": "logging.NullHandler"
        }
        config["handlers"]["sql_file"] = {
            "class": "logging.NullHandler"
        }
    
    # Add web-specific loggers
    config["loggers"].update({
        "uvicorn": {
            "handlers": ["console"],
            "level": settings.get_component_log_level("uvicorn"),
            "propagate": False
        },
        "uvicorn.error": {
            "handlers": ["console"],
            "level": settings.get_component_log_level("uvicorn.error"),
            "propagate": False
        },
        "uvicorn.access": {
            "handlers": ["null"],
            "level": settings.get_component_log_level("uvicorn.access"),
            "propagate": False
        },
        # Configure app loggers
        "app": {
            "handlers": ["console", "file"],
            "level": settings.get_log_level,
            "propagate": False
        },
        "app.api": {
            "handlers": ["console", "file"],
            "level": settings.get_log_level,
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
    
    config["handlers"].update({
        "cli_file": get_file_handler(str(cli_log_file), "detailed")
    })
    
    # Update loggers for CLI
    config["loggers"].update({
        "app.cli": {
            "handlers": ["console", "cli_file"],
            "level": settings.get_component_log_level("app.cli"),
            "propagate": False
        }
    })
    
    return config