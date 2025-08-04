"""Echo the output."""

from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt


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
        self.print(f"💀\t[bold red]{add_tabs(message)}[/]")

    def confirm(self, message: str, **kwargs: Any) -> bool:
        """Prompt the user for confirmation."""
        if "default" not in kwargs:
            kwargs["default"] = False

        return Confirm.ask(prompt=f"❓\t[blue]{add_tabs(message)}[/]", **kwargs)

    def prompt(self, message: str, **kwargs: Any) -> Any:
        """Prompt the user for value."""
        return Prompt.ask(prompt=f"❓\t[blue]{add_tabs(message)}[/]", show_default=True, **kwargs)


echo = Echo()
