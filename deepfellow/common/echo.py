"""Echo the output."""

import click
from rich.console import Console


def add_tabs(msg: str) -> str:
    """Add tabs at the beginning of the message for alignment."""
    return msg.replace("\n", "\n\t")


class Echo(Console):
    def debug(self, message: str) -> None:
        """Print a debug message to the console."""
        ctx = click.get_current_context()
        if ctx and ctx.obj.get("debug"):
            self.print(f"🔍\t[grey]{add_tabs(message)}[/]", style="dim white")

    def info(self, message: str) -> None:
        """Print a success message to the console."""
        self.print(f"💡\t{add_tabs(message)}")

    def success(self, message: str) -> None:
        """Print a success message to the console."""
        self.print(f"✅\t[green]{add_tabs(message)}[/]")

    def warning(self, message: str) -> None:
        """Print a warning message to the console."""
        self.print(f"⚠️\t[yellow]{add_tabs(message)}[/]")

    def error(self, message: str) -> None:
        """Print an error message to the console."""
        self.print(f"💀\t[red]{add_tabs(message)}[/]")


echo = Echo()
