import typer
from rich.console import Console
from app.core.logging.management import LogManager
from app.core.config import settings

app = typer.Typer(help="Manage log files")
console = Console()

@app.command()
def rotate():
    """Manually rotate all log files."""
    manager = LogManager()
    log_types = ['app', 'audit', 'cli', 'sql']
    
    for log_type in log_types:
        for env in ['development', 'production', 'test']:
            name = f"{log_type}_{env}"
            manager.rotate_log(name)
    
    console.print("[green]Log rotation completed successfully[/green]")

@app.command()
def cleanup():
    """Clean up old log files."""
    manager = LogManager()
    manager.cleanup_old_logs()
    console.print("[green]Old logs cleaned up successfully[/green]")