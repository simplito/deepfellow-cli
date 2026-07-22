# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common exceptions."""

import functools
from collections.abc import Callable
from typing import NoReturn, ParamSpec

import typer

from deepfellow.common.echo import echo
from deepfellow.common.state import state

P = ParamSpec("P")


class DockerSocketNotFoundError(Exception):
    """Raised if docker.sock file not found."""


class DockerNetworkError(Exception):
    """Raised if getting a list of networks fails."""


class InstallError(Exception):
    """Raised by an install() core function to signal a validation or setup failure.

    Unlike ``typer.Exit`` (an exit code with no message), ``InstallError`` carries a
    human-readable message, so it is safe to catch and act on outside a Click/Typer
    dispatch context — e.g. by an in-process caller such as ``suite install``.
    """


def reraise_if_debug(exc_info: Exception) -> NoReturn:
    """Re-raise the active exception if debug mode is enabled, otherwise exit with code 1.

    Must be called from within an ``except`` block: the debug path uses a bare ``raise`` and
    therefore re-raises the currently handled exception, not necessarily ``exc_info``.
    """
    if state.debug:
        raise

    raise typer.Exit(1) from exc_info


def translate_to_install_error(func: Callable[P, None]) -> Callable[P, None]:
    """Make an install() core function safe to call outside a Click/Typer dispatch loop.

    ``typer.Exit`` and ``typer.BadParameter`` are only safe error signals inside a Click
    dispatch loop: ``typer.Exit`` carries no message, and both are otherwise unhandled,
    message-less exceptions to a plain in-process caller. This decorator catches both,
    however deep they were raised (directly, or transitively via ``assert_docker``,
    ``ensure_directory``, ``echo.prompt*``, ...), and re-raises ``InstallError(message)``
    instead. ``BadParameter``'s message is never echoed by its raise site, so it is echoed
    here to preserve today's CLI console output; ``typer.Exit`` raise sites already echo
    their reason before raising, so it is not echoed twice.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            func(*args, **kwargs)
        except typer.BadParameter as exc:
            message = str(exc)
            echo.error(message)
            raise InstallError(message) from exc
        except typer.Exit as exc:
            raise InstallError("Installation failed; see console output above for details.") from exc

    return wrapper
