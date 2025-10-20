"""Echo the output."""

from collections.abc import Callable
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

type ValidationCallback = Callable[[str | None], str | None] | None


def add_tabs(msg: str) -> str:
    """Add tabs at the beginning of the message for alignment."""
    return msg.replace("\n", "\n\t")


class Echo(Console):
    def debug(self, message_source: Any) -> None:
        """Print a debug message to the console."""
        ctx = click.get_current_context()
        message = str(message_source)
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

    def prompt(self, message: str, validation: ValidationCallback = None, **kwargs: Any) -> Any:
        """Prompt the user for value."""
        value = Prompt.ask(prompt=f"❓\t[blue]{add_tabs(message)}[/]", show_default=True, **kwargs)
        if validation is not None:
            value = validation(value)

        return value


echo = Echo()
