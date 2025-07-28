"""Echo the output."""

import typer
from rich.console import Console


class Echo(Console):
    def debug(self, message: str, ctx: typer.Context | None = None) -> None:
        """Print a debug message to the console."""
        if ctx and ctx.obj.get("debug"):
            self.print(f"🔍\t[grey]{message}[/]", style="dim white")

    def info(self, message: str, _: typer.Context | None = None) -> None:
        """Print a success message to the console."""
        self.print(f"💡\t{message}")

    def success(self, message: str, _: typer.Context | None = None) -> None:
        """Print a success message to the console."""
        self.print(f"✅\t[green]{message}[/]")

    def warning(self, message: str, _: typer.Context | None = None) -> None:
        """Print a warning message to the console."""
        self.print(f"⚠️\t[yellow]{message}[/]")

    def error(self, message: str, _: typer.Context | None = None) -> None:
        """Print an error message to the console."""
        self.print(f"❌\t[red]{message}[/]")


echo = Echo()
