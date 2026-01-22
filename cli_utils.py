#!/usr/bin/env python3
"""CLI utilities using Rich for formatted output."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.spinner import SPINNERS
from rich import box

# Global console instance
console = Console()

# Register custom WTP spinner
# Cycles through circle/dot characters with fire gradient (yellow -> orange -> red)
# Colors match banner.py: yellow=93m, orange=38;5;208, red=91m
YELLOW = "\033[1;93m"
ORANGE = "\033[1;38;5;208m"
RED = "\033[1;91m"
RST = "\033[0m"

SPINNERS["wtp"] = {
    "frames": [
        f"{YELLOW}●{RST}",
        f"{YELLOW}◉{RST}",
        f"{ORANGE}○{RST}",
        f"{ORANGE}◌{RST}",
        f"{RED}⁘{RST}",
        f"{RED}⁙{RST}",
        f"{ORANGE}※{RST}",
        f"{YELLOW}⁜{RST}",
    ],
    "interval": 120,
}


def print_error(message: str, details: list[str] | None = None):
    """Print an error message in a red panel."""
    content = f"[red]{message}[/red]"
    if details:
        content += "\n\n" + "\n".join(f"  [dim]{i+1}.[/dim] {d}" for i, d in enumerate(details))
    console.print(Panel(content, title="[bold red]Error[/bold red]", border_style="red"))


def print_cli_error(message: str, hints: list[str] | None = None):
    """Print a lightweight CLI error message (no panel).

    Consistent with argparse error styling:
    - Bold red "Error:" prefix
    - Message text
    - Optional hints in dim text
    """
    console.print()
    console.print(f"[bold red]Error:[/bold red] {message}")
    if hints:
        console.print()
        for hint in hints:
            console.print(f"  [dim]{hint}[/dim]")
    console.print()


def print_warning(message: str):
    """Print a warning message in a yellow panel."""
    console.print(Panel(f"[yellow]{message}[/yellow]", title="[bold yellow]Warning[/bold yellow]", border_style="yellow"))


def print_success(message: str, details: dict | None = None):
    """Print a success message in a green panel."""
    content = f"[green]{message}[/green]"
    if details:
        content += "\n"
        for key, value in details.items():
            content += f"\n[dim]{key}:[/dim] {value}"
    console.print(Panel(content, title="[bold green]Done[/bold green]", border_style="green"))


def print_info(message: str):
    """Print an info message."""
    console.print(f"[dim]{message}[/dim]")


def print_panel(content: str, title: str, border_style: str = "blue"):
    """Print content in a panel."""
    console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style=border_style))


def create_key_value_table() -> Table:
    """Create a table for key-value pairs (no headers)."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="dim")
    table.add_column("Value")
    return table


def create_status_table(headers: list[str]) -> Table:
    """Create a table for status display with headers."""
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    for header in headers:
        if header == "Status":
            table.add_column(header, justify="center")
        elif header == "#":
            table.add_column(header, justify="right", style="dim")
        else:
            table.add_column(header)
    return table


def format_status(status: str, is_ok: bool) -> str:
    """Format a status string with appropriate color."""
    if is_ok:
        return f"[green]{status}[/green]"
    return f"[red]{status}[/red]"


def format_active(text: str) -> str:
    """Format text to show it's the active/selected item."""
    return f"[bold]{text}[/bold]"


def format_dim(text: str) -> str:
    """Format text as dimmed."""
    return f"[dim]{text}[/dim]"


def format_highlight(text: str) -> str:
    """Format text as highlighted (cyan)."""
    return f"[cyan]{text}[/cyan]"


def format_value(text: str, style: str = "default") -> str:
    """Format a value with the given style."""
    styles = {
        "default": text,
        "success": f"[green]{text}[/green]",
        "error": f"[red]{text}[/red]",
        "warning": f"[yellow]{text}[/yellow]",
        "highlight": f"[cyan]{text}[/cyan]",
        "bold": f"[bold]{text}[/bold]",
        "dim": f"[dim]{text}[/dim]",
        "magenta": f"[bold magenta]{text}[/bold magenta]",
    }
    return styles.get(style, text)


def get_progress_spinner():
    """Get a progress spinner context manager with custom WTP! branding."""
    return Progress(
        SpinnerColumn(spinner_name="wtp"),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )


def print_commands(commands: list[tuple[str, str]]):
    """Print a list of commands with descriptions."""
    console.print()
    console.print("[dim]Quick commands:[/dim]")
    for cmd, desc in commands:
        console.print(f"  [cyan]{cmd}[/cyan]  {desc}")


def confirm(prompt: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    suffix = " [Y/n]" if default else " [y/N]"
    response = console.input(f"{prompt}{suffix} ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes")
