# /markitdown-service/app/core/logging/management.py
import os
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import fcntl
from app.core.config import settings

class LogManager:
    def __init__(self, log_dir: str = settings.LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.settings = settings

    def get_log_path(self, name: str, date: Optional[datetime] = None) -> Path:
        """Get path for a log file with optional date suffix."""
        if date:
            return self.log_dir / f"{name}_{date.strftime('%Y-%m-%d')}.log"
        return self.log_dir / f"{name}.log"

    def get_retention_days(self, log_type: str) -> int:
        """Get the environment-adjusted retention period for a specific log type."""
        base_days = self.settings.LOG_RETENTION_DAYS.get(log_type, 30)
        multiplier = self.settings.LOG_RETENTION_MULTIPLIERS.get(
            self.settings.ENVIRONMENT, 
            1.0
        )
        return int(base_days * multiplier)

    def rotate_log(self, name: str) -> None:
        """Rotate a log file, compressing the old one."""
        current = self.get_log_path(name)
        if not current.exists():
            return

        # Lock the file during rotation
        with open(current, 'a') as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                # Check file size before rotating
                if current.stat().st_size == 0:
                    return

                # Rotate
                today = datetime.now()
                rotated = self.get_log_path(name, today)

                # Copy content and truncate original
                shutil.copy2(current, rotated)
                with open(current, 'w') as cf:
                    pass

                # Compress rotated file if enabled
                if self.settings.LOG_COMPRESSION_ENABLED:
                    with open(rotated, 'rb') as f_in:
                        gz_path = str(rotated) + '.gz'
                        with gzip.open(gz_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    rotated.unlink()

            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def cleanup_old_logs(self) -> None:
        """Remove log files older than retention period based on log type and environment."""
        now = datetime.now()

        for file in self.log_dir.glob('*.log.gz'):
            try:
                # Extract log type and date from filename
                filename_parts = file.stem.split('_')
                if len(filename_parts) < 2:
                    continue

                log_type = filename_parts[0]
                date_str = filename_parts[-1]

                # Get environment-adjusted retention period
                retention_days = self.get_retention_days(log_type)
                cutoff = now - timedelta(days=retention_days)

                try:
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    # Try alternate date format (for older logs)
                    try:
                        file_date = datetime.strptime(date_str.split('-')[0], '%Y%m%d')
                    except ValueError:
                        continue

                if file_date < cutoff:
                    file.unlink()
            except (ValueError, IndexError):
                continue

    def get_log_size(self, name: str) -> int:
        """Get the current size of a log file in bytes."""
        path = self.get_log_path(name)
        try:
            return path.stat().st_size
        except FileNotFoundError:
            return 0

    def should_rotate(self, name: str) -> bool:
        """Check if a log file should be rotated based on size."""
        max_size_str = self.settings.LOG_ROTATION_MAX_SIZE
        # Convert max size string (e.g., "100M") to bytes
        size_units = {'K': 1024, 'M': 1024*1024, 'G': 1024*1024*1024}
        unit = max_size_str[-1].upper()
        max_size = int(max_size_str[:-1]) * size_units.get(unit, 1)
        
        return self.get_log_size(name) >= max_size