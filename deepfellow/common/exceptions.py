# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common exceptions."""

import click
import typer


class ConfigValidationError(Exception):
    """Raised when config validation is failing."""


class DockerSocketNotFoundError(Exception):
    """Raised if docker.sock file not found."""


class DockerNetworkError(Exception):
    """Raised if getting a list of networks fails."""


def reraise_if_debug(exc_info: Exception) -> None:
    """Reraise the exception if debug in Context."""
    ctx = click.get_current_context()
    if ctx.obj.get("debug", False):
        raise

    raise typer.Exit(1) from exc_info
