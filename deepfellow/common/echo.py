# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
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
import questionary
import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from deepfellow.common.colors import COLORS, RESET

ValidationCallback = Callable[[Any], Any] | None


def add_tabs(msg: str) -> str:
    """Add tabs at the beginning of the message for alignment."""
    return msg.replace("\n", "\n\t")


def is_interactive() -> bool:
    """Check if in interactive mode."""
    try:
        ctx = click.get_current_context()
        return bool(ctx and not ctx.obj.get("non-interactive", False))
    except RuntimeError:
        return True


class Echo(Console):
    def debug(self, message_source: Any) -> None:
        """Print a debug message to the console."""
        ctx = click.get_current_context()
        message = str(message_source)
        if ctx and ctx.obj.get("debug"):
            final_msg = f"🔍\t[grey]{add_tabs(message)}[/]" if is_interactive() else message
            self.print(final_msg, style="dim white")

    def info(self, message: str) -> None:
        """Print a success message to the console."""
        final_msg = f"💡\t{add_tabs(message)}" if is_interactive() else message
        self.print(final_msg)

    def success(self, message: str) -> None:
        """Print a success message to the console."""
        final_msg = f"✅\t[green]{add_tabs(message)}[/]" if is_interactive() else message
        self.print(final_msg)

    def warning(self, message: str) -> None:
        """Print a warning message to the console."""
        final_msg = f"⚠️\t[yellow]{add_tabs(message)}[/]" if is_interactive() else message
        self.print(final_msg)

    def error(self, message: str) -> None:
        """Print an error message to the console."""
        final_msg = f"💀\t[bold red]{add_tabs(message)}[/]" if is_interactive() else message
        self.print(final_msg)

    def confirm(self, message: str, **kwargs: Any) -> bool:
        """Prompt the user for confirmation."""
        if "default" not in kwargs:
            kwargs["default"] = False

        if not is_interactive():
            return kwargs["default"]

        final_msg = f"❓\t{COLORS.medium_blue}{add_tabs(message)}{RESET}" if is_interactive() else message
        return Confirm.ask(prompt=final_msg, **kwargs)

    def prompt(
        self,
        message: str,
        validation: ValidationCallback = None,
        from_args: Any = None,
        original_default: Any = None,
        *,
        default: Any = None,
        password: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Prompt the user for value.

        Logic:
            - Non-interactive mode: returns explicit CLI value if provided,
              otherwise returns default, or exits with an error if no default.
            - Interactive mode: asks user when no CLI value was provided or the
              provided value equals the default. Uses CLI value without asking
              when explicitly provided.
            - Validation: if a callback is provided, passes the value through it.
              Invalid value raises BadParameter.

        Args:
            message: The prompt message to display
            validation: Optional callback to validate/transform the value
            from_args: Value provided via CLI arguments
            original_default: The original default value for comparison
            default: Value read from configuration, or fallback from CLI argument
            password: If True, mask the input and default value display
            **kwargs: Additional arguments passed to Prompt.ask

        Returns:
            The final value (from args, user input, or default)
        """
        has_user_provided_value = from_args is not None and from_args != original_default
        return_value = from_args if has_user_provided_value else None

        if not is_interactive():
            # Determine the return value
            if has_user_provided_value:
                return_value = from_args
            elif default is not None:
                return_value = default
            else:
                echo.error(f"Non interactive mode is ON.\nPlease provide the value in args.\nMSG: {message}")
                raise typer.Exit(1)

        # We do not ask user if value is provided in CLI
        if return_value is not None:
            return return_value

        # Interactive mode - ask user
        show_default = True

        if password and default:
            default = str(default)
            masked_password = f"{default[0:2]}***{default[-2:]}"
            message = message + f" \x1b[36m[bold]({masked_password})[/bold]{RESET}"
            show_default = False

        # int value where not shown in Prompt.ask's message
        if isinstance(default, int):
            default = str(default)

        value = Prompt.ask(
            prompt=f"❓\t{COLORS.medium_blue}{add_tabs(message)}{RESET}",
            default=default,
            password=password,
            show_default=show_default,
            **kwargs,
        )

        if validation is not None:
            value = validation(value)

        return value

    def prompt_until_valid(
        self,
        message: str,
        validation: ValidationCallback,
        error_message: str | None = None,
        from_args: Any = None,
        original_default: Any = None,
        *,
        default: Any = None,
        password: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Prompt until input is valid.

        Wraps prompt() with a retry loop for interactive mode validation errors.
        Non-interactive mode and CLI-provided values are handled by prompt() directly.

        Args:
            message: The prompt message to display
            validation: Callback to validate/transform the value (required)
            error_message: Custom error message on validation failure
            from_args: Value provided via CLI arguments
            original_default: The original default value for comparison
            default: Value read from configuration, or fallback from CLI argument
            password: If True, mask the input and default value display
            **kwargs: Additional arguments passed to Prompt.ask

        Returns:
            The validated value
        """
        while True:
            try:
                return self.prompt(
                    message,
                    validation=validation,
                    from_args=from_args,
                    original_default=original_default,
                    default=default,
                    password=password,
                    **kwargs,
                )
            except typer.BadParameter as exc:
                if not is_interactive():
                    raise

                self.error(error_message or str(exc))
                # Clear from_args to force prompting on retry
                from_args = None

    def choice(
        self,
        message: str,
        choices: list[str] | list[Any],
        default: Any = None,
        **kwargs: Any,
    ) -> str:
        """Prompt the user to make a choice from a list of options."""
        if not is_interactive():
            if default is not None:
                return default

            echo.error(f"Non interactive mode is ON.\nPlease provide the value in args.\nMSG: {message}")
            raise typer.Exit(1)

        final_msg = f"{add_tabs(message)}" if is_interactive() else message
        return questionary.select(final_msg, choices=choices, default=default, **kwargs).ask()


echo = Echo()
