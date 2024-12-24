from typing import Optional, Dict, Any
import typer
from rich.console import Console
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
from app.cli.utils.menu_utils import (
    handle_numeric_input,
    safe_menu_action,
    with_confirmation,
    handle_menu_input,
    format_table_row
)

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
    LOGS_MENU = "Log Management"
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
        choice = handle_menu_input(
            "\n[cyan]Select an option[/cyan]",
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
        choice = handle_menu_input(
            "\n[cyan]Select an option[/cyan]",
            choices=valid_inputs
        )
        
        # Convert number input to menu choice
        if choice.isdigit() and choice in choice_map:
            return choice_map[choice]
        # Direct menu choice value
        elif choice in LogMenuChoice._value2member_map_:
            return LogMenuChoice(choice)
        
        console.print("[red]Invalid choice. Please try again.[/red]")

@safe_menu_action
def create_user_menu():
    """Interactive menu for creating a new user."""
    name = handle_menu_input("[cyan]Enter name for the user[/cyan]", [])
    email = handle_menu_input("[cyan]Enter email address[/cyan]", [])
    
    with_confirmation(
        "create user with these settings",
        user_commands.create,
        name=name,
        email=email
    )

@safe_menu_action
def list_users_menu():
    """Interactive menu for listing users."""
    show_inactive = handle_menu_input(
        "[cyan]Show inactive users?[/cyan]",
        choices=["y", "n"],
        default="n"
    ) == "y"
    
    format_output = handle_menu_input(
        "[cyan]Output format[/cyan]",
        choices=["table", "json"],
        default="table"
    )
    
    typer.echo()
    user_commands.list(
        show_inactive=show_inactive,
        format_type=format_output
    )

@safe_menu_action
def view_user_menu():
    """Interactive menu for viewing user details."""
    user_id = handle_numeric_input("[cyan]Enter user ID to view[/cyan]")
    typer.echo()
    user_commands.info(user_id=user_id)

@safe_menu_action
def manage_user_status_menu():
    """Interactive menu for managing user status."""
    user_id = handle_numeric_input("[cyan]Enter user ID[/cyan]")
    action = handle_menu_input(
        "[cyan]Choose action[/cyan]",
        choices=["activate", "deactivate"]
    )
    
    typer.echo()
    if action == "activate":
        with_confirmation(
            f"activate user {user_id}",
            user_commands.activate,
            user_id=user_id,
            force=True
        )
    else:
        with_confirmation(
            f"deactivate user {user_id}",
            user_commands.deactivate,
            user_id=user_id,
            force=True
        )

@safe_menu_action
def create_key_menu():
    """Interactive menu for creating a new API key."""
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
            table.add_row(*format_table_row(
                user.id, user.name, user.email,
                styles=["cyan", "green", "blue"]
            ))
        
        console.print(table)
    
    user_id = handle_numeric_input("[cyan]Enter user ID for the key[/cyan]")
    name = handle_menu_input("[cyan]Enter name for the key[/cyan]", [])
    role_str = handle_menu_input(
        "[cyan]Select role[/cyan]",
        choices=["admin", "user"],
        default="user"
    )
    
    # Convert string role to Role enum
    role = Role.ADMIN if role_str.lower() == "admin" else Role.USER
    
    with_confirmation(
        "create API key with these settings",
        api_key_commands.create,
        name=name,
        role=role,
        user_id=user_id
    )

@safe_menu_action
def list_keys_menu():
    """Interactive menu for listing API keys."""
    show_inactive = handle_menu_input(
        "[cyan]Show inactive keys?[/cyan]",
        choices=["y", "n"],
        default="n"
    ) == "y"
    
    format_output = handle_menu_input(
        "[cyan]Output format[/cyan]",
        choices=["table", "json"],
        default="table"
    )
    
    typer.echo()
    api_key_commands.list(
        show_inactive=show_inactive,
        format=format_output
    )

@safe_menu_action
def deactivate_key_menu():
    """Interactive menu for deactivating an API key."""
    key_id = handle_numeric_input("[cyan]Enter API key ID to deactivate[/cyan]")
    
    with_confirmation(
        f"deactivate key {key_id}",
        api_key_commands.deactivate,
        key_id=key_id,
        force=True
    )

@safe_menu_action
def reactivate_key_menu():
    """Interactive menu for reactivating an API key."""
    key_id = handle_numeric_input("[cyan]Enter API key ID to reactivate[/cyan]")
    
    with_confirmation(
        f"reactivate key {key_id}",
        api_key_commands.reactivate,
        key_id=key_id,
        force=True
    )

@safe_menu_action
def view_key_menu():
    """Interactive menu for viewing API key details."""
    key_id = handle_numeric_input("[cyan]Enter API key ID to view[/cyan]")
    typer.echo()
    api_key_commands.info(key_id=key_id)

@safe_menu_action
def log_management_menu():
    """Interactive menu for log management."""
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
            with_confirmation(
                "rotate all log files now",
                log_commands.rotate
            )
        elif choice == LogMenuChoice.CLEANUP_LOGS:
            with_confirmation(
                "clean up old log files",
                log_commands.cleanup
            )
        
        if choice != LogMenuChoice.BACK:
            handle_menu_input("\n[cyan]Press Enter to continue[/cyan]", [""])

@safe_menu_action
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
                handle_menu_input("\n[cyan]Press Enter to continue[/cyan]", [""])
                
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")

app = typer.Typer()

@app.command()
def main():
    """Launch interactive management menu."""
    interactive_menu()

if __name__ == "__main__":
    app()
