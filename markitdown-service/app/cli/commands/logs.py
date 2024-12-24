# /markitdown-service/app/cli/commands/logs.py
import typer
from rich.console import Console
from rich.table import Table
from pathlib import Path
from datetime import datetime
from app.core.logging.management import LogManager
from app.core.config import settings

app = typer.Typer(help="Manage log files")
console = Console()

@app.command()
def rotate():
    """Manually rotate all log files."""
    manager = LogManager()
    log_types = ['app', 'audit', 'cli', 'sql']
    
    with console.status("[bold green]Rotating logs...") as status:
        for log_type in log_types:
            for env in ['development', 'production', 'test']:
                try:
                    name = f"{log_type}_{env}"
                    manager.rotate_log(name)
                    status.update(f"[bold green]Rotated {name}")
                except Exception as e:
                    console.print(f"[bold red]Error rotating {name}: {str(e)}")
    
    console.print("[green]Log rotation completed successfully[/green]")

@app.command()
def cleanup(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cleanup of all rotated logs regardless of age"
    )
):
    """Clean up old log files."""
    try:
        manager = LogManager()
        manager.cleanup_logs(force=force)
        console.print("[green]Old logs cleaned up successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error cleaning up logs: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def status():
    """Show current log files and retention settings."""
    table = Table(title="Log Management Status")
    table.add_column("Log Type", style="cyan")
    table.add_column("Environment", style="green")
    table.add_column("Retention Days", style="yellow")
    table.add_column("Current Size", style="magenta")
    table.add_column("Last Modified", style="blue")

    manager = LogManager()
    log_dir = Path(settings.LOG_DIR)

    for log_type in settings.LOG_RETENTION_DAYS.keys():
        for env in ['development', 'production', 'test']:
            name = f"{log_type}_{env}"
            log_file = log_dir / f"{name}.log"
            retention = settings.get_retention_days(log_type)
            
            size = "0 B"
            last_modified = "N/A"
            
            if log_file.exists():
                # Get file size
                bytes_size = log_file.stat().st_size
                if bytes_size < 1024:
                    size = f"{bytes_size} B"
                elif bytes_size < 1024 * 1024:
                    size = f"{bytes_size/1024:.1f} KB"
                else:
                    size = f"{bytes_size/(1024*1024):.1f} MB"
                
                # Get last modified time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                last_modified = mtime.strftime("%Y-%m-%d %H:%M:%S")

            table.add_row(log_type, env, str(retention), size, last_modified)

    console.print(table)

@app.command()
def list():
    """List all log files in the log directory."""
    log_dir = Path(settings.LOG_DIR)
    
    table = Table(title="Log Files")
    table.add_column("Filename", style="cyan")
    table.add_column("Size", style="green")
    table.add_column("Created", style="yellow")
    
    if not log_dir.exists():
        console.print("[red]Log directory does not exist[/red]")
        return
        
    files = sorted(log_dir.glob('*.log*'))
    
    for file in files:
        size = file.stat().st_size
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size/1024:.1f} KB"
        else:
            size_str = f"{size/(1024*1024):.1f} MB"
            
        created = datetime.fromtimestamp(file.stat().st_ctime)
        created_str = created.strftime("%Y-%m-%d %H:%M:%S")
        
        table.add_row(file.name, size_str, created_str)
    
    console.print(table)