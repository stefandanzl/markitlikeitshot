from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from enum import Enum
from app.cli.commands import api_key as api_key_commands
from app.cli.commands import user as user_commands
from app.cli.commands import logs as log_commands
from app.models.auth.api_key import Role
from app.models.auth.user import User, UserStatus
from app.db.session import get_db_session
from sqlmodel import select
import logging
from app.cli.manage import display_version_info

# Initialize console and logger
console = Console()
logger = logging.getLogger(__name__)

class MenuChoice(str, Enum):
    LIST_USERS = "List Users"
    CREATE_USER = "Create New User"
    VIEW_USER = "View User Details"
    MANAGE_USER_STATUS = "Manage User Status"
    LIST_KEYS = "List API Keys"
    CREATE_KEY = "Create New API Key"
    DEACTIVATE_KEY = "Deactivate API Key"
    REACTIVATE_KEY = "Reactivate API Key"
    VIEW_KEY = "View Key Details"
    LOGS_MENU = "Log Management"  # Changed from ROTATE_LOGS to LOGS_MENU
    VERSION = "Show Version Info"
    EXIT = "Exit"

class LogMenuChoice(str, Enum):
    VIEW_STATUS = "View Log Status"
    LIST_FILES = "List Log Files"
    ROTATE_LOGS = "Rotate Logs"
    CLEANUP_LOGS = "Clean Up Old Logs"
    BACK = "Back to Main Menu"

def display_menu() -> MenuChoice:
    """Display main menu and return user choice."""
    console.print("\n[bold blue]MarkItDown Management[/bold blue]")
    
    table = Table(
        show_header=False,
        border_style="blue",
        box=None,
        padding=(0, 2)
    )
    table.add_column("Option", style="cyan")
    
    # Create a mapping of numbers to choices
    choice_map = {str(i): choice for i, choice in enumerate(MenuChoice, 1)}
    
    for num, choice in choice_map.items():
        table.add_row(f"{num}. {choice.value}")
    
    console.print(Panel(table, border_style="blue"))
    
    # Allow both number and full text input
    valid_inputs = list(choice_map.keys()) + [choice.value for choice in MenuChoice]
    
    while True:
        choice = Prompt.ask(
            "\n[cyan]Select an option[/cyan]",
            show_choices=True,
            choices=valid_inputs
        )
        
        # Convert number input to menu choice
        if choice.isdigit() and choice in choice_map:
            return choice_map[choice]
        # Direct menu choice value
        elif choice in MenuChoice._value2member_map_:
            return MenuChoice(choice)
        
        console.print("[red]Invalid choice. Please try again.[/red]")

def display_log_menu() -> LogMenuChoice:
    """Display log management menu and return user choice."""
    console.print("\n[bold blue]Log Management[/bold blue]")
    
    table = Table(
        show_header=False,
        border_style="blue",
        box=None,
        padding=(0, 2)
    )
    table.add_column("Option", style="cyan")
    
    # Create a mapping of numbers to choices
    choice_map = {str(i): choice for i, choice in enumerate(LogMenuChoice, 1)}
    
    for num, choice in choice_map.items():
        table.add_row(f"{num}. {choice.value}")
    
    console.print(Panel(table, border_style="blue"))
    
    # Allow both number and full text input
    valid_inputs = list(choice_map.keys()) + [choice.value for choice in LogMenuChoice]
    
    while True:
        choice = Prompt.ask(
            "\n[cyan]Select an option[/cyan]",
            show_choices=True,
            choices=valid_inputs
        )
        
        # Convert number input to menu choice
        if choice.isdigit() and choice in choice_map:
            return choice_map[choice]
        # Direct menu choice value
        elif choice in LogMenuChoice._value2member_map_:
            return LogMenuChoice(choice)
        
        console.print("[red]Invalid choice. Please try again.[/red]")

def create_user_menu():
    """Interactive menu for creating a new user."""
    try:
        name = Prompt.ask("[cyan]Enter name for the user[/cyan]")
        email = Prompt.ask("[cyan]Enter email address[/cyan]")
        
        if Confirm.ask("[cyan]Create user with these settings?[/cyan]"):
            typer.echo()
            user_commands.create(
                name=name,
                email=email
            )
    except Exception as e:
        logger.exception("Failed to create user")
        console.print(f"[red]Error creating user: {str(e)}[/red]")

def list_users_menu():
    """Interactive menu for listing users."""
    try:
        show_inactive = Confirm.ask(
            "[cyan]Show inactive users?[/cyan]",
            default=False
        )
        
        format_output = Prompt.ask(
            "[cyan]Output format[/cyan]",
            choices=["table", "json"],
            default="table"
        )
        
        typer.echo()
        user_commands.list(
            show_inactive=show_inactive,
            format_type=format_output
        )
    except Exception as e:
        logger.exception("Failed to list users")
        console.print(f"[red]Error listing users: {str(e)}[/red]")

def view_user_menu():
    """Interactive menu for viewing user details."""
    try:
        user_id_str = Prompt.ask("[cyan]Enter user ID to view[/cyan]")
        try:
            user_id = int(user_id_str)
            typer.echo()
            user_commands.info(user_id=user_id)
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to view user")
        console.print(f"[red]Error viewing user: {str(e)}[/red]")

def manage_user_status_menu():
    """Interactive menu for managing user status."""
    try:
        user_id_str = Prompt.ask("[cyan]Enter user ID[/cyan]")
        try:
            user_id = int(user_id_str)
            action = Prompt.ask(
                "[cyan]Choose action[/cyan]",
                choices=["activate", "deactivate"]
            )
            
            if Confirm.ask(f"[yellow]Are you sure you want to {action} user {user_id}?[/yellow]"):
                typer.echo()
                if action == "activate":
                    user_commands.activate(user_id=user_id, force=True)
                else:
                    user_commands.deactivate(user_id=user_id, force=True)
                    
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to manage user status")
        console.print(f"[red]Error managing user status: {str(e)}[/red]")

def log_management_menu():
    """Interactive menu for log management."""
    try:
        while True:
            choice = display_log_menu()
            
            if choice == LogMenuChoice.BACK:
                break
            
            typer.echo()
            
            if choice == LogMenuChoice.VIEW_STATUS:
                log_commands.status()
            elif choice == LogMenuChoice.LIST_FILES:
                log_commands.list()
            elif choice == LogMenuChoice.ROTATE_LOGS:
                if Confirm.ask("[cyan]Rotate all log files now?[/cyan]"):
                    log_commands.rotate()
            elif choice == LogMenuChoice.CLEANUP_LOGS:
                if Confirm.ask("[yellow]Clean up old log files?[/yellow]"):
                    log_commands.cleanup()
            
            if choice != LogMenuChoice.BACK:
                Prompt.ask("\n[cyan]Press Enter to continue[/cyan]")
                
    except Exception as e:
        logger.exception("Log management error")
        console.print(f"[red]Error in log management: {str(e)}[/red]")

def create_key_menu():
    """Interactive menu for creating a new API key."""
    try:
        # First, list available users
        console.print("\n[cyan]Available Users:[/cyan]")
        with get_db_session() as db:
            query = select(User).where(User.status == UserStatus.ACTIVE)
            users = db.exec(query).all()
            
            if not users:
                console.print("[yellow]No active users found[/yellow]")
                return
            
            # Display users in a simple table
            table = Table(title="Active Users")
            table.add_column("ID", style="cyan")
            table.add_column("Name", style="green")
            table.add_column("Email", style="blue")
            
            for user in users:
                table.add_row(str(user.id), user.name, user.email)
            
            console.print(table)
        
        user_id_str = Prompt.ask("[cyan]Enter user ID for the key[/cyan]")
        try:
            user_id = int(user_id_str)
            name = Prompt.ask("[cyan]Enter name for the key[/cyan]")
            role_str = Prompt.ask(
                "[cyan]Select role[/cyan]",
                choices=["admin", "user"],
                default="user"
            )
            
            # Convert string role to Role enum
            role = Role.ADMIN if role_str.lower() == "admin" else Role.USER
            
            if Confirm.ask("[cyan]Create API key with these settings?[/cyan]"):
                typer.echo()
                api_key_commands.create(
                    name=name,
                    role=role,
                    user_id=user_id
                )
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to create API key")
        console.print(f"[red]Error creating API key: {str(e)}[/red]")

def list_keys_menu():
    """Interactive menu for listing API keys."""
    try:
        show_inactive = Confirm.ask(
            "[cyan]Show inactive keys?[/cyan]",
            default=False
        )
        
        format_output = Prompt.ask(
            "[cyan]Output format[/cyan]",
            choices=["table", "json"],
            default="table"
        )
        
        typer.echo()
        api_key_commands.list(
            show_inactive=show_inactive,
            format=format_output
        )
    except Exception as e:
        logger.exception("Failed to list API keys")
        console.print(f"[red]Error listing API keys: {str(e)}[/red]")

def deactivate_key_menu():
    """Interactive menu for deactivating an API key."""
    try:
        key_id_str = Prompt.ask("[cyan]Enter API key ID to deactivate[/cyan]")
        try:
            key_id = int(key_id_str)
            
            if Confirm.ask(f"[yellow]Are you sure you want to deactivate key {key_id}?[/yellow]"):
                typer.echo()
                api_key_commands.deactivate(
                    key_id=key_id,
                    force=True
                )
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to deactivate API key")
        console.print(f"[red]Error deactivating API key: {str(e)}[/red]")

def reactivate_key_menu():
    """Interactive menu for reactivating an API key."""
    try:
        key_id_str = Prompt.ask("[cyan]Enter API key ID to reactivate[/cyan]")
        try:
            key_id = int(key_id_str)
            
            if Confirm.ask(f"[yellow]Are you sure you want to reactivate key {key_id}?[/yellow]"):
                typer.echo()
                api_key_commands.reactivate(
                    key_id=key_id,
                    force=True
                )
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to reactivate API key")
        console.print(f"[red]Error reactivating API key: {str(e)}[/red]")

def view_key_menu():
    """Interactive menu for viewing API key details."""
    try:
        key_id_str = Prompt.ask("[cyan]Enter API key ID to view[/cyan]")
        try:
            key_id = int(key_id_str)
            typer.echo()
            api_key_commands.info(key_id=key_id)
        except ValueError:
            console.print("[red]Invalid input: Please enter a valid number[/red]")
    except Exception as e:
        logger.exception("Failed to view API key")
        console.print(f"[red]Error viewing API key: {str(e)}[/red]")

def interactive_menu():
    """Main interactive menu loop."""
    try:
        while True:
            choice = display_menu()
            
            if choice == MenuChoice.EXIT:
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            typer.echo()  # Add blank line before command output
            
            if choice == MenuChoice.LIST_USERS:
                list_users_menu()
            elif choice == MenuChoice.CREATE_USER:
                create_user_menu()
            elif choice == MenuChoice.VIEW_USER:
                view_user_menu()
            elif choice == MenuChoice.MANAGE_USER_STATUS:
                manage_user_status_menu()
            elif choice == MenuChoice.LIST_KEYS:
                list_keys_menu()
            elif choice == MenuChoice.CREATE_KEY:
                create_key_menu()
            elif choice == MenuChoice.DEACTIVATE_KEY:
                deactivate_key_menu()
            elif choice == MenuChoice.REACTIVATE_KEY:
                reactivate_key_menu()
            elif choice == MenuChoice.VIEW_KEY:
                view_key_menu()
            elif choice == MenuChoice.LOGS_MENU:
                log_management_menu()
            elif choice == MenuChoice.VERSION:
                display_version_info()
            
            if choice != MenuChoice.EXIT:
                Prompt.ask("\n[cyan]Press Enter to continue[/cyan]")
                
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    except Exception as e:
        logger.exception("Interactive menu error")
        console.print(f"[red]An error occurred: {str(e)}[/red]")
        raise typer.Exit(1)

app = typer.Typer()

@app.command()
def main():
    """Launch interactive management menu."""
    interactive_menu()

if __name__ == "__main__":
    app()