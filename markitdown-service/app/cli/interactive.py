from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from enum import Enum
from app.cli.commands import api_key as api_key_commands
from app.models.auth.api_key import Role
import logging
from app.cli.manage import display_version_info

# Initialize console and logger
console = Console()
logger = logging.getLogger(__name__)

class MenuChoice(str, Enum):
    LIST_KEYS = "List API Keys"
    CREATE_KEY = "Create New API Key"
    DEACTIVATE_KEY = "Deactivate API Key"
    REACTIVATE_KEY = "Reactivate API Key"
    VIEW_KEY = "View Key Details"
    VERSION = "Show Version Info"
    EXIT = "Exit"

def display_menu() -> MenuChoice:
    """Display main menu and return user choice."""
    console.print("\n[bold blue]MarkItDown API Key Management[/bold blue]")
    
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
            "\n[cyan]Select an option[/cyan] (1-7)",
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

def create_key_menu():
    """Interactive menu for creating a new API key."""
    try:
        name = Prompt.ask("[cyan]Enter name for the key[/cyan]")
        role = Prompt.ask(
            "[cyan]Select role[/cyan]",
            choices=["admin", "user"],
            default="user"
        )
        description = Prompt.ask(
            "[cyan]Enter description (optional)[/cyan]",
            default=""
        )
        
        if Confirm.ask("[cyan]Create API key with these settings?[/cyan]"):
            typer.echo()
            api_key_commands.create(
                name=name,
                role=role,
                description=description
            )
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
        
        role_filter = Prompt.ask(
            "[cyan]Filter by role[/cyan]",
            choices=["admin", "user", "all"],
            default="all"
        )
        
        format_output = Prompt.ask(
            "[cyan]Output format[/cyan]",
            choices=["table", "json"],
            default="table"
        )
        
        typer.echo()
        api_key_commands.list(
            show_inactive=show_inactive,
            role=None if role_filter == "all" else role_filter,
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
                    force=True  # Skip second confirmation
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
                    force=True  # Skip second confirmation
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
            
            if choice == MenuChoice.LIST_KEYS:
                list_keys_menu()
            elif choice == MenuChoice.CREATE_KEY:
                create_key_menu()
            elif choice == MenuChoice.DEACTIVATE_KEY:
                deactivate_key_menu()
            elif choice == MenuChoice.REACTIVATE_KEY:
                reactivate_key_menu()
            elif choice == MenuChoice.VIEW_KEY:
                view_key_menu()
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
    """Launch interactive API key management menu."""
    interactive_menu()

if __name__ == "__main__":
    app()