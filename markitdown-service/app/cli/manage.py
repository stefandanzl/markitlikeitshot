import typer
from app.cli.commands import api_key
from app.db.init_db import init_db
from app.db.session import get_db_session
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from typing import Optional, Dict
import IPython
import logging
import logging.config
import os
from pathlib import Path
from datetime import datetime
from app.core.config import settings

app = typer.Typer(
    help="MarkItDown API Management CLI",
    no_args_is_help=True
)
app.add_typer(api_key.app, name="apikeys", help="Manage API keys")
console = Console()

# Initialize module-specific loggers
logger = logging.getLogger(__name__)
cli_logger = logging.getLogger("app.cli")
db_logger = logging.getLogger("app.db")

def get_cli_logging_config(quiet: bool = False) -> Dict:
    """Get CLI-specific logging configuration."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    cli_log_file = log_dir / f"cli_{datetime.now().strftime('%Y%m%d')}.log"
    sql_log_file = log_dir / f"sql_{datetime.now().strftime('%Y%m%d')}.log"
    
    return {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "cli": {
                "format": "%(levelname)s: %(message)s" if not quiet else "%(message)s"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "cli",
                "level": "DEBUG" if settings.ENVIRONMENT == "development" else "INFO"
            },
            "file": {
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
            },
            "null": {
                "class": "logging.NullHandler"
            }
        },
        "loggers": {
            "app.cli": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False
            },
            "app.db": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False
            },
            "sqlalchemy": {
                "handlers": ["sql_file"],
                "level": "INFO",
                "propagate": False
            },
            "sqlalchemy.engine": {
                "handlers": ["sql_file"],
                "level": "INFO",
                "propagate": False
            },
            "": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            }
        }
    }

def setup_logging(quiet: bool = False):
    """
    Configure logging for the CLI.
    
    Args:
        quiet (bool): If True, sets more restrictive logging for interactive CLI
    """
    # Apply CLI-specific logging configuration
    logging.config.dictConfig(get_cli_logging_config(quiet))
    
    # Log startup information
    cli_logger.debug(f"CLI logging initialized (quiet={quiet})")
    cli_logger.debug(f"Environment: {settings.ENVIRONMENT}")
    cli_logger.debug(f"Log Level: {settings.LOG_LEVEL}")

def setup_shell_logging():
    """Configure quieter logging for shell sessions"""
    setup_logging(quiet=True)
    cli_logger.debug("Shell logging initialized")

def display_version_info():
    """Display version information in a table."""
    table = Table(show_header=False)
    table.add_column("Component", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Version", settings.VERSION)
    table.add_row("Environment", settings.ENVIRONMENT)
    table.add_row("Log Level", settings.LOG_LEVEL)
    table.add_row("API Auth Enabled", str(settings.API_KEY_AUTH_ENABLED))
    table.add_row("Database URL", settings.DATABASE_URL)
    table.add_row("Rate Limit", f"{settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_PERIOD}")
    table.add_row("Max File Size", f"{settings.MAX_FILE_SIZE / (1024*1024):.1f} MB")
    
    console.print(Panel(
        table,
        title="MarkItDown Service Information",
        border_style="blue"
    ))
    
    # Log version check
    cli_logger.info(f"Version information displayed: {settings.VERSION}")

@app.callback()
def callback(
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Reduce logging output"
    ),
    log_level: str = typer.Option(
        None,
        "--log-level",
        "-l",
        help="Override default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
):
    """
    MarkItDown API Management CLI
    """
    # Override log level if specified
    if log_level:
        os.environ["LOG_LEVEL"] = log_level.upper()
    
    setup_logging(quiet=quiet)
    cli_logger.debug(f"CLI started with quiet={quiet}, log_level={log_level or settings.LOG_LEVEL}")
    
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
        
        cli_logger.info("Starting database initialization")
        
        # Ensure directories exist
        for dir_name in ["data", "logs"]:
            os.makedirs(dir_name, exist_ok=True)
            cli_logger.debug(f"Ensured directory exists: {dir_name}")
        
        with console.status("[bold blue]Initializing database...") as status:
            with get_db_session() as db:
                cli_logger.debug("Creating database tables...")
                init_db(db)
                status.update("[bold blue]Creating initial admin key...")
                cli_logger.info("Database initialization completed")
        
        console.print(Panel(
            "[green]Database initialized successfully![/green]\n"
            "Use 'python manage.py apikeys create' to create new API keys.",
            title="Initialization Complete",
            border_style="green"
        ))
    except Exception as e:
        error_msg = f"Database initialization failed: {str(e)}"
        console.print(f"[red]{error_msg}[/red]")
        cli_logger.error(error_msg, exc_info=True)
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
        cli_logger.info("Starting interactive shell")
        setup_shell_logging()
        
        # Import commonly needed objects
        from app.models.auth.api_key import APIKey, Role
        from app.core.security.api_key import create_api_key
        from sqlmodel import select
        
        # Create context dictionary with a new database session
        with get_db_session() as db:
            context = {
                'settings': settings,
                'APIKey': APIKey,
                'Role': Role,
                'create_api_key': create_api_key,
                'select': select,
                'db': db,
                'console': console,
                'get_db_session': get_db_session,
                'logger': cli_logger  # Add logger to context
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
• get_db_session: Database session context manager
• logger: CLI logger instance

Example usage:
>>> with get_db_session() as db:
...     keys = db.exec(select(APIKey)).all()
...     console.print(keys)
"""
            
            cli_logger.debug("Launching IPython shell")
            IPython.embed(
                banner1=banner,
                colors="neutral",
                user_ns=context
            )
    except Exception as e:
        error_msg = f"Shell launch failed: {str(e)}"
        console.print(f"[red]{error_msg}[/red]")
        cli_logger.error(error_msg, exc_info=True)
        raise typer.Exit(1)

@app.command()
def version():
    """Display version information."""
    cli_logger.debug("Displaying version information")
    display_version_info()

@app.command()
def check(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to fix any issues found"
    )
):
    """Check system configuration and dependencies."""
    cli_logger.info(f"Starting system check (fix={fix})")
    with console.status("[bold blue]Checking system...") as status:
        checks = []
        
        # Check database connection
        try:
            with get_db_session() as db:
                db.execute("SELECT 1")
                checks.append(("Database Connection", True, "Connected"))
                cli_logger.debug("Database connection check passed")
        except Exception as e:
            error_msg = f"Database connection failed: {str(e)}"
            cli_logger.error(error_msg)
            checks.append(("Database Connection", False, str(e)))
            if fix:
                try:
                    status.update("Attempting to initialize database...")
                    cli_logger.info("Attempting database fix")
                    with get_db_session() as db:
                        init_db(db)
                    checks.append(("Database Fix", True, "Initialized successfully"))
                    cli_logger.info("Database fix successful")
                except Exception as fix_e:
                    error_msg = f"Database fix failed: {str(fix_e)}"
                    cli_logger.error(error_msg)
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
                        cli_logger.info(f"Creating missing directory: {dir_name}")
                        dir_path.mkdir(parents=True)
                        checks.append((f"Created {dir_name}", True, purpose))
                    else:
                        cli_logger.warning(f"Missing directory: {dir_name}")
                        checks.append((f"Directory: {dir_name}", False, f"Missing - {purpose}"))
                else:
                    # Check permissions
                    readable = os.access(dir_path, os.R_OK)
                    writable = os.access(dir_path, os.W_OK)
                    if readable and writable:
                        cli_logger.debug(f"Directory check passed: {dir_name}")
                        checks.append((f"Directory: {dir_name}", True, f"Ready - {purpose}"))
                    else:
                        cli_logger.error(f"Permission denied for directory: {dir_name}")
                        checks.append((f"Directory: {dir_name}", False, "Permission denied"))
            except Exception as e:
                error_msg = f"Directory check failed for {dir_name}: {str(e)}"
                cli_logger.error(error_msg)
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
    failed_checks = total_checks - passed_checks
    
    summary = Panel(
        f"[cyan]Total Checks:[/cyan] {total_checks}\n"
        f"[green]Passed:[/green] {passed_checks}\n"
        f"[red]Failed:[/red] {failed_checks}",
        title="Check Summary",
        border_style="blue"
    )
    console.print(summary)
    
    cli_logger.info(f"System check completed: {passed_checks}/{total_checks} passed")
    
    if failed_checks > 0:
        if fix:
            cli_logger.warning("Some issues could not be automatically fixed")
            console.print("[yellow]Some issues could not be automatically fixed.[/yellow]")
        else:
            cli_logger.info("Suggesting --fix option for failed checks")
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
        
        cli_logger.info("Starting cleanup process")
        with console.status("[bold blue]Cleaning up...") as status:
            # Clean old logs
            log_dir = Path("logs")
            if log_dir.exists():
                from datetime import timedelta
                
                retention = timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
                cutoff = datetime.now() - retention
                
                cleaned = 0
                for log_file in log_dir.glob("*.log"):
                    try:
                        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                        if mtime < cutoff:
                            cli_logger.debug(f"Removing old log file: {log_file}")
                            log_file.unlink()
                            cleaned += 1
                    except Exception as e:
                        error_msg = f"Failed to process {log_file}: {e}"
                        cli_logger.warning(error_msg)
                
                status.update(f"[bold blue]Cleaned {cleaned} old log files")
                cli_logger.info(f"Cleaned {cleaned} old log files")
        
        console.print("[green]Cleanup completed successfully![/green]")
    
    except Exception as e:
        error_msg = f"Cleanup failed: {str(e)}"
        console.print(f"[red]{error_msg}[/red]")
        cli_logger.error(error_msg, exc_info=True)
        raise typer.Exit(1)

@app.command()
def interactive():
    """Launch interactive API key management interface."""
    cli_logger.info("Starting interactive mode")
    setup_logging(quiet=True)
    from app.cli.interactive import interactive_menu
    interactive_menu()

if __name__ == "__main__":
    app()