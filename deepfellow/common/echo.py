"""Echo the output."""

import click
from rich.console import Console


class Echo(Console):
    def debug(self, message: str) -> None:
        """Print a debug message to the console."""
        ctx = click.get_current_context()
        if ctx and ctx.obj.get("debug"):
            self.print(f"🔍\t[grey]{message}[/]", style="dim white")

    def info(self, message: str) -> None:
        """Print a success message to the console."""
        self.print(f"💡\t{message}")

    def success(self, message: str) -> None:
        """Print a success message to the console."""
        self.print(f"✅\t[green]{message}[/]")

    def warning(self, message: str) -> None:
        """Print a warning message to the console."""
        self.print(f"⚠️\t[yellow]{message}[/]")

    def error(self, message: str) -> None:
        """Print an error message to the console."""
        self.print(f"❌\t[red]{message}[/]")


echo = Echo()
