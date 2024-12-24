from typing import TypeVar, Callable, Optional, Any
from rich.console import Console
from rich.prompt import Prompt
import logging
from functools import wraps

console = Console()
logger = logging.getLogger(__name__)

T = TypeVar('T')

def handle_numeric_input(prompt: str, error_msg: Optional[str] = None) -> int:
    """
    Handle numeric input with validation and error handling.
    
    Args:
        prompt: The prompt to display to the user
        error_msg: Optional custom error message for invalid input
        
    Returns:
        int: The validated numeric input
        
    Raises:
        ValueError: If the input cannot be converted to an integer
    """
    try:
        value = int(Prompt.ask(prompt))
        return value
    except ValueError:
        error = error_msg or "[red]Invalid input: Please enter a valid number[/red]"
        console.print(error)
        raise

def safe_menu_action(func: Callable[..., T]) -> Callable[..., Optional[T]]:
    """
    Decorator for safely executing menu actions with error handling.
    
    Args:
        func: The function to wrap
        
    Returns:
        The wrapped function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Optional[T]:
        try:
            return func(*args, **kwargs)
        except ValueError:
            # Already handled by handle_numeric_input
            return None
        except Exception as e:
            logger.exception(f"Error in menu action {func.__name__}")
            console.print(f"[red]Error: {str(e)}[/red]")
            return None
    return wrapper

def with_confirmation(
    action: str,
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any
) -> Optional[T]:
    """
    Execute a function with user confirmation.
    
    Args:
        action: Description of the action requiring confirmation
        func: Function to execute
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function
        
    Returns:
        The result of the function if confirmed, None otherwise
    """
    if Prompt.ask(f"[cyan]Are you sure you want to {action}?[/cyan]", choices=["y", "n"], default="n") == "y":
        return func(*args, **kwargs)
    return None

def handle_menu_input(
    prompt: str,
    choices: list[str],
    default: Optional[str] = None
) -> str:
    """
    Handle menu input with choices.
    
    Args:
        prompt: The prompt to display
        choices: List of valid choices
        default: Optional default choice
        
    Returns:
        str: The selected choice
    """
    return Prompt.ask(
        prompt,
        choices=choices,
        default=default or choices[0]
    )

def format_table_row(
    *values: Any,
    styles: Optional[list[str]] = None
) -> tuple[str, ...]:
    """
    Format values for table display with optional styling.
    
    Args:
        *values: Values to format
        styles: Optional list of Rich styles to apply
        
    Returns:
        Tuple of formatted strings
    """
    if not styles:
        return tuple(str(v) for v in values)
        
    formatted = []
    for value, style in zip(values, styles + [''] * (len(values) - len(styles))):
        formatted.append(f"[{style}]{value}[/{style}]" if style else str(value))
    return tuple(formatted)
