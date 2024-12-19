import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from sqlmodel import Session, select, create_engine
from app.core.config import settings
from app.models.auth.api_key import Role, APIKey
from app.core.security.api_key import create_api_key
from datetime import datetime
import logging

app = typer.Typer(help="Manage API keys")
console = Console()
logger = logging.getLogger(__name__)

def get_db():
    engine = create_engine(settings.DATABASE_URL)
    with Session(engine) as session:
        yield session

@app.command()
def create(
    name: str = typer.Option(..., help="Name for the API key"),
    role: Role = typer.Option(Role.USER, help="Role for the API key"),
    description: str = typer.Option(None, help="Optional description")
):
    """Create a new API key"""
    try:
        db = next(get_db())
        api_key = create_api_key(db, name=name, role=role)
        
        table = Table(title="New API Key Created", show_header=False, title_style="bold green")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Name", api_key.name)
        table.add_row("Key", api_key.key)
        table.add_row("Role", api_key.role)
        table.add_row("Created", str(api_key.created_at))
        
        console.print(Panel(
            table,
            title="API Key Created Successfully",
            border_style="green"
        ))
        
        # Important security notice
        console.print("\n[yellow]⚠️  Important:[/yellow] Store this API key securely - it won't be shown again!")
        
    except Exception as e:
        logger.exception("Failed to create API key")
        console.print(f"[red]Error creating API key: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def list(
    show_inactive: bool = typer.Option(False, help="Show inactive keys"),
    role: Role = typer.Option(None, help="Filter by role"),
    format: str = typer.Option("table", help="Output format (table/json)")
):
    """List all API keys"""
    try:
        db = next(get_db())
        query = select(APIKey)
        
        if not show_inactive:
            query = query.where(APIKey.is_active == True)
        if role:
            query = query.where(APIKey.role == role)
            
        api_keys = db.exec(query).all()
        
        if not api_keys:
            console.print("[yellow]No API keys found[/yellow]")
            return
        
        if format.lower() == "json":
            import json
            keys_data = [
                {
                    "id": key.id,
                    "name": key.name,
                    "role": key.role,
                    "created_at": key.created_at.isoformat(),
                    "last_used": key.last_used.isoformat() if key.last_used else None,
                    "is_active": key.is_active
                }
                for key in api_keys
            ]
            console.print_json(json.dumps(keys_data, indent=2))
            return
        
        table = Table(
            title="API Keys",
            show_lines=True,
            title_style="bold blue"
        )
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Role", style="blue")
        table.add_column("Created", style="magenta")
        table.add_column("Last Used", style="yellow")
        table.add_column("Status", style="red")
        
        for key in api_keys:
            table.add_row(
                str(key.id),
                key.name,
                key.role,
                str(key.created_at.strftime("%Y-%m-%d %H:%M")),
                str(key.last_used.strftime("%Y-%m-%d %H:%M")) if key.last_used else "Never",
                "🟢 Active" if key.is_active else "🔴 Inactive"
            )
        
        console.print(table)
        
    except Exception as e:
        logger.exception("Failed to list API keys")
        console.print(f"[red]Error listing API keys: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def deactivate(
    key_id: int = typer.Argument(..., help="ID of the API key to deactivate"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Deactivate an API key"""
    try:
        if not force and not Confirm.ask(f"Are you sure you want to deactivate API key {key_id}?"):
            raise typer.Abort()
            
        db = next(get_db())
        api_key = db.get(APIKey, key_id)
        
        if not api_key:
            console.print(f"[red]API key with ID {key_id} not found[/red]")
            raise typer.Exit(1)
            
        api_key.is_active = False
        db.commit()
        
        console.print(Panel(
            f"Successfully deactivated API key: {api_key.name}",
            style="green"
        ))
        
    except Exception as e:
        logger.exception(f"Failed to deactivate API key {key_id}")
        console.print(f"[red]Error deactivating API key: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def reactivate(
    key_id: int = typer.Argument(..., help="ID of the API key to reactivate"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Reactivate an API key"""
    try:
        if not force and not Confirm.ask(f"Are you sure you want to reactivate API key {key_id}?"):
            raise typer.Abort()
            
        db = next(get_db())
        api_key = db.get(APIKey, key_id)
        
        if not api_key:
            console.print(f"[red]API key with ID {key_id} not found[/red]")
            raise typer.Exit(1)
            
        api_key.is_active = True
        db.commit()
        
        console.print(Panel(
            f"Successfully reactivated API key: {api_key.name}",
            style="green"
        ))
        
    except Exception as e:
        logger.exception(f"Failed to reactivate API key {key_id}")
        console.print(f"[red]Error reactivating API key: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def info(
    key_id: int = typer.Argument(..., help="ID of the API key to show")
):
    """Show detailed information about an API key"""
    try:
        db = next(get_db())
        api_key = db.get(APIKey, key_id)
        
        if not api_key:
            console.print(f"[red]API key with ID {key_id} not found[/red]")
            raise typer.Exit(1)
        
        table = Table(show_header=False, title=f"API Key Details: {api_key.name}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("ID", str(api_key.id))
        table.add_row("Name", api_key.name)
        table.add_row("Role", api_key.role)
        table.add_row("Status", "Active" if api_key.is_active else "Inactive")
        table.add_row("Created", str(api_key.created_at))
        table.add_row("Last Used", str(api_key.last_used) if api_key.last_used else "Never")
        
        console.print(table)
        
    except Exception as e:
        logger.exception(f"Failed to show API key info for {key_id}")
        console.print(f"[red]Error showing API key info: {str(e)}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()