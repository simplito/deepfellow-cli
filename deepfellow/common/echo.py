# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Echo the output."""

from collections.abc import Callable
from typing import Any

import click
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from deepfellow.common.colors import COLORS, RESET

ValidationCallback = Callable[[str | None], str | None] | None


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

        return Confirm.ask(prompt=f"❓\t{COLORS.medium_blue}{add_tabs(message)}{RESET}", **kwargs)

    def prompt(self, message: str, validation: ValidationCallback = None, **kwargs: Any) -> Any:
        """Prompt the user for value."""
        value = Prompt.ask(prompt=f"❓\t{COLORS.medium_blue}{add_tabs(message)}{RESET}", show_default=True, **kwargs)
        if validation is not None:
            value = validation(value)

        return value

    def prompt_until_valid(
        self,
        message: str,
        validation: ValidationCallback,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Prompt until input is valid."""
        response: Any = None
        while not response:
            try:
                response = echo.prompt(message, validation=validation, **kwargs)
            except typer.BadParameter as exc:
                echo.error(error_message or str(exc))

        return response


echo = Echo()
