import typer
from app.cli.commands import api_key
from app.db.init_db import init_db
from app.db.session import get_db
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from typing import Optional
import IPython
import logging
import os
from pathlib import Path
from datetime import datetime

app = typer.Typer(
    help="MarkItDown API Management CLI",
    no_args_is_help=True
)
app.add_typer(api_key.app, name="apikeys", help="Manage API keys")
console = Console()

# Set up logging
logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging for the CLI"""
    from app.core.config import settings
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"cli_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format=settings.LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

@app.callback()
def callback():
    """
    MarkItDown API Management CLI
    """
    setup_logging()
    console.print(
        Panel.fit(
            "MarkItDown API Management",
            style="bold blue"
        )
    )

@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force initialization even if database exists"
    ),
    skip_confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt"
    )
):
    """Initialize the database and create initial admin API key."""
    try:
        if not (force or skip_confirm) and not Confirm.ask(
            "This will initialize/reset the database. Are you sure?"
        ):
            raise typer.Abort()
        
        # Ensure directories exist
        for dir_name in ["data", "logs"]:
            os.makedirs(dir_name, exist_ok=True)
        
        with console.status("[bold blue]Initializing database...") as status:
            db = next(get_db())
            init_db(db)
            status.update("[bold blue]Creating initial admin key...")
        
        console.print(Panel(
            "[green]Database initialized successfully![/green]\n"
            "Use 'python manage.py apikeys create' to create new API keys.",
            title="Initialization Complete",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[red]Error initializing database: {str(e)}[/red]")
        logger.exception("Database initialization failed")
        raise typer.Exit(1)

@app.command()
def shell(
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Start shell without banner"
    )
):
    """Launch an interactive shell with pre-loaded context."""
    try:
        # Import commonly needed objects
        from app.core.config import settings
        from app.models.auth.api_key import APIKey, Role
        from app.core.security.api_key import create_api_key
        from sqlmodel import select
        
        # Create context dictionary
        context = {
            'settings': settings,
            'APIKey': APIKey,
            'Role': Role,
            'create_api_key': create_api_key,
            'select': select,
            'db': next(get_db()),
            'console': console
        }
        
        banner = "" if quiet else f"""
╔══════════════════════════════════════════╗
║        MarkItDown Management Shell       ║
╚══════════════════════════════════════════╝

Available objects:
• settings: Application settings
• APIKey: API key model
• Role: API key roles
• create_api_key: Function to create new API keys
• select: SQLModel select function
• db: Database session
• console: Rich console for formatted output

Example usage:
>>> keys = db.exec(select(APIKey)).all()
>>> console.print(keys)
"""
        
        IPython.embed(
            banner1=banner,
            colors="neutral",
            user_ns=context
        )
    except Exception as e:
        console.print(f"[red]Error launching shell: {str(e)}[/red]")
        logger.exception("Shell launch failed")
        raise typer.Exit(1)

@app.command()
def version():
    """Display version information."""
    from app.core.config import settings
    
    table = Table(show_header=False)
    table.add_column("Component", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Version", settings.VERSION)
    table.add_row("Environment", settings.ENVIRONMENT)
    table.add_row("API Auth Enabled", str(settings.API_KEY_AUTH_ENABLED))
    table.add_row("Database URL", settings.DATABASE_URL)
    table.add_row("Rate Limit", f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_WINDOW}s")
    table.add_row("Max File Size", f"{settings.MAX_FILE_SIZE / (1024*1024):.1f} MB")
    
    console.print(Panel(
        table,
        title="MarkItDown Service Information",
        border_style="blue"
    ))

@app.command()
def check(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to fix any issues found"
    )
):
    """Check system configuration and dependencies."""
    from app.core.config import settings
    
    with console.status("[bold blue]Checking system...") as status:
        checks = []
        
        # Check database connection
        try:
            db = next(get_db())
            db.execute("SELECT 1")
            checks.append(("Database Connection", True, "Connected"))
        except Exception as e:
            checks.append(("Database Connection", False, str(e)))
            if fix:
                try:
                    status.update("Attempting to initialize database...")
                    init_db(db)
                    checks.append(("Database Fix", True, "Initialized successfully"))
                except Exception as fix_e:
                    checks.append(("Database Fix", False, str(fix_e)))
        
        # Check directories and permissions
        required_dirs = {
            "data": "Database and storage",
            "logs": "Application logs",
        }
        
        for dir_name, purpose in required_dirs.items():
            dir_path = Path(dir_name)
            try:
                if not dir_path.exists():
                    if fix:
                        dir_path.mkdir(parents=True)
                        checks.append((f"Created {dir_name}", True, purpose))
                    else:
                        checks.append((f"Directory: {dir_name}", False, f"Missing - {purpose}"))
                else:
                    # Check permissions
                    readable = os.access(dir_path, os.R_OK)
                    writable = os.access(dir_path, os.W_OK)
                    if readable and writable:
                        checks.append((f"Directory: {dir_name}", True, f"Ready - {purpose}"))
                    else:
                        checks.append((f"Directory: {dir_name}", False, "Permission denied"))
            except Exception as e:
                checks.append((f"Directory: {dir_name}", False, str(e)))
    
    # Display results
    table = Table(title="System Check Results")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    
    for component, status, details in checks:
        status_symbol = "✓" if status else "✗"
        status_style = "green" if status else "red"
        table.add_row(
            component,
            f"[{status_style}]{status_symbol}[/{status_style}]",
            details
        )
    
    console.print(table)
    
    # Summary
    total_checks = len(checks)
    passed_checks = sum(1 for _, status, _ in checks if status)
    
    console.print(Panel(
        f"[cyan]Total Checks:[/cyan] {total_checks}\n"
        f"[green]Passed:[/green] {passed_checks}\n"
        f"[red]Failed:[/red] {total_checks - passed_checks}",
        title="Check Summary",
        border_style="blue"
    ))
    
    if not all(status for _, status, _ in checks):
        if fix:
            console.print("[yellow]Some issues could not be automatically fixed.[/yellow]")
        else:
            console.print("[yellow]Run with --fix to attempt automatic fixes.[/yellow]")
        raise typer.Exit(1)

@app.command()
def clean(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force cleanup without confirmation"
    )
):
    """Clean temporary files and logs."""
    try:
        if not force and not Confirm.ask(
            "This will delete temporary files and old logs. Continue?"
        ):
            raise typer.Abort()
        
        with console.status("[bold blue]Cleaning up...") as status:
            # Clean old logs
            log_dir = Path("logs")
            if log_dir.exists():
                from app.core.config import settings
                from datetime import timedelta
                
                retention = timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
                cutoff = datetime.now() - retention
                
                cleaned = 0
                for log_file in log_dir.glob("*.log"):
                    try:
                        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if mtime < cutoff:
                            log_file.unlink()
                            cleaned += 1
                    except Exception as e:
                        logger.warning(f"Failed to process {log_file}: {e}")
                
                status.update(f"[bold blue]Cleaned {cleaned} old log files")
        
        console.print("[green]Cleanup completed successfully![/green]")
    
    except Exception as e:
        console.print(f"[red]Error during cleanup: {str(e)}[/red]")
        logger.exception("Cleanup failed")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()