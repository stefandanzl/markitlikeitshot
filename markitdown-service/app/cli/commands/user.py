import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from sqlmodel import select
from app.models.auth.user import User, UserStatus
from app.core.security.user import create_user, get_user
from app.db.session import get_db_session
from app.models.auth.api_key import Role
import logging

app = typer.Typer(help="Manage users")
console = Console()
logger = logging.getLogger(__name__)

@app.command()
def create(
    name: str = typer.Option(..., help="Name of the user"),
    email: str = typer.Option(..., help="Email address"),
):
    """Create a new user"""
    try:
        with get_db_session() as db:
            user = create_user(
                db=db,
                name=name,
                email=email,
            )
            
            table = Table(title="New User Created", show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("ID", str(user.id))
            table.add_row("Name", user.name)
            table.add_row("Email", user.email)
            table.add_row("Status", user.status)
            table.add_row("Created", str(user.created_at))
            
            console.print(Panel(table, title="User Created Successfully", border_style="green"))
            
    except Exception as e:
        logger.exception("Failed to create user")
        console.print(f"[red]Error creating user: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def list(
    show_inactive: bool = typer.Option(False, help="Show inactive users"),
    format_type: str = typer.Option("table", "--format", "-f", help="Output format (table/json)")
):
    """List all users"""
    try:
        with get_db_session() as db:
            query = select(User)
            if not show_inactive:
                query = query.where(User.status == UserStatus.ACTIVE)
            
            users = db.execute(query).scalars().all()
            
            if not users:
                console.print(Panel(
                    "[yellow]No users found[/yellow]",
                    title="Users",
                    border_style="blue"
                ))
                return
            
            if format_type == "json":
                import json
                users_data = [
                    {
                        "id": user.id,
                        "name": user.name,
                        "email": user.email,
                        "status": user.status.value,
                        "created_at": user.created_at.isoformat(),
                        "api_key_count": len(user.api_keys),
                        "active_api_keys": sum(1 for key in user.api_keys if key.is_active)
                    }
                    for user in users
                ]
                console.print_json(json.dumps(users_data, indent=2))
                return
            
            table = Table(
                title="Users",
                show_lines=True,
                title_style="bold blue"
            )
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Email", style="blue")
            table.add_column("Status", style="yellow")
            table.add_column("Created", style="magenta")
            table.add_column("API Keys", style="cyan", justify="center")
            
            for user in users:
                active_keys = sum(1 for key in user.api_keys if key.is_active)
                total_keys = len(user.api_keys)
                api_key_display = f"{active_keys}/{total_keys}"
                
                table.add_row(
                    str(user.id),
                    user.name,
                    user.email,
                    "🟢 Active" if user.status == UserStatus.ACTIVE else "🔴 Inactive",
                    str(user.created_at.strftime("%Y-%m-%d %H:%M")),
                    api_key_display
                )
            
            console.print(Panel(
                table,
                title="User Management",
                border_style="blue",
                padding=(1, 2)
            ))
            
    except Exception as e:
        logger.exception("Failed to list users")
        console.print(f"[red]Error listing users: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def info(user_id: int = typer.Argument(..., help="ID of the user to show")):
    """Show detailed information about a user"""
    try:
        with get_db_session() as db:
            user = get_user(db, user_id)
            
            if not user:
                console.print(f"[red]User with ID {user_id} not found[/red]")
                raise typer.Exit(1)
            
            # User details table
            user_table = Table(show_header=False)
            user_table.add_column("Field", style="cyan")
            user_table.add_column("Value", style="green")
            
            user_table.add_row("ID", str(user.id))
            user_table.add_row("Name", user.name)
            user_table.add_row("Email", user.email)
            user_table.add_row("Status", "🟢 Active" if user.status == UserStatus.ACTIVE else "🔴 Inactive")
            user_table.add_row("Created", str(user.created_at))
            
            # Add API key summary
            active_keys = sum(1 for key in user.api_keys if key.is_active)
            admin_keys = sum(1 for key in user.api_keys if key.role == Role.ADMIN)
            user_keys = sum(1 for key in user.api_keys if key.role == Role.USER)
            
            user_table.add_section()  # Add a visual separator
            user_table.add_row("Total API Keys", str(len(user.api_keys)))
            user_table.add_row("Active Keys", str(active_keys))
            user_table.add_row("Admin Keys", str(admin_keys))
            user_table.add_row("User Keys", str(user_keys))
            
            console.print(Panel(user_table, title="User Details", border_style="blue"))
            
            # API Keys table
            if user.api_keys:
                key_table = Table(
                    show_header=True,
                    show_lines=True,
                    title_style="bold blue"
                )
                key_table.add_column("ID", style="cyan", no_wrap=True)
                key_table.add_column("Name", style="green")
                key_table.add_column("Role", style="blue")
                key_table.add_column("Status", style="yellow")
                key_table.add_column("Created", style="magenta")
                key_table.add_column("Last Used", style="magenta")
                
                for key in user.api_keys:
                    key_table.add_row(
                        str(key.id),
                        key.name,
                        key.role.value,
                        "🟢 Active" if key.is_active else "🔴 Inactive",
                        str(key.created_at.strftime("%Y-%m-%d %H:%M")),
                        str(key.last_used.strftime("%Y-%m-%d %H:%M")) if key.last_used else "Never"
                    )
                
                console.print(Panel(
                    key_table,
                    title="API Keys",
                    border_style="blue",
                    padding=(1, 2)
                ))
            else:
                console.print(Panel(
                    "[yellow]No API keys found for this user[/yellow]",
                    title="API Keys",
                    border_style="blue"
                ))
            
    except Exception as e:
        logger.exception(f"Failed to show user info for {user_id}")
        console.print(f"[red]Error showing user info: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def deactivate(
    user_id: int = typer.Argument(..., help="ID of the user to deactivate"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Deactivate a user and all their API keys"""
    try:
        if not force and not Confirm.ask(f"Are you sure you want to deactivate user {user_id}?"):
            raise typer.Abort()
            
        with get_db_session() as db:
            user = get_user(db, user_id)
            
            if not user:
                console.print(f"[red]User with ID {user_id} not found[/red]")
                raise typer.Exit(1)
            
            user.status = UserStatus.INACTIVE
            # Deactivate all API keys
            for key in user.api_keys:
                key.is_active = False
            
            db.commit()
            
            console.print(Panel(
                f"Successfully deactivated user: {user.name} and all their API keys",
                style="green"
            ))
            
    except Exception as e:
        logger.exception(f"Failed to deactivate user {user_id}")
        console.print(f"[red]Error deactivating user: {str(e)}[/red]")
        raise typer.Exit(1)

@app.command()
def activate(
    user_id: int = typer.Argument(..., help="ID of the user to activate"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Activate a user (does not reactivate API keys)"""
    try:
        if not force and not Confirm.ask(f"Are you sure you want to activate user {user_id}?"):
            raise typer.Abort()
            
        with get_db_session() as db:
            user = get_user(db, user_id)
            
            if not user:
                console.print(f"[red]User with ID {user_id} not found[/red]")
                raise typer.Exit(1)
            
            user.status = UserStatus.ACTIVE
            db.commit()
            
            console.print(Panel(
                f"Successfully activated user: {user.name}\n"
                "Note: API keys remain in their current state",
                style="green"
            ))
            
    except Exception as e:
        logger.exception(f"Failed to activate user {user_id}")
        console.print(f"[red]Error activating user: {str(e)}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
