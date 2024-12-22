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
        
    def get_log_path(self, name: str, date: Optional[datetime] = None) -> Path:
        """Get path for a log file with optional date suffix."""
        if date:
            return self.log_dir / f"{name}_{date.strftime('%Y-%m-%d')}.log"
        return self.log_dir / f"{name}.log"
    
    def rotate_log(self, name: str) -> None:
        """Rotate a log file, compressing the old one."""
        current = self.get_log_path(name)
        if not current.exists():
            return
            
        # Lock the file during rotation
        with open(current, 'a') as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                # Rotate
                today = datetime.now()
                rotated = self.get_log_path(name, today)
                
                # Rename current to dated file
                current.rename(rotated)
                
                # Compress rotated file
                with open(rotated, 'rb') as f_in:
                    gz_path = str(rotated) + '.gz'
                    with gzip.open(gz_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed rotated file
                rotated.unlink()
                
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def cleanup_old_logs(self, retention_days: int = settings.AUDIT_LOG_RETENTION_DAYS) -> None:
        """Remove log files older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        for file in self.log_dir.glob('*.log.gz'):
            try:
                # Extract date from filename
                date_str = file.stem.split('_')[-1]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if file_date < cutoff:
                    file.unlink()
            except (ValueError, IndexError):
                continue