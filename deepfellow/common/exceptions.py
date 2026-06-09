# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Common exceptions."""

import typer

from deepfellow.common.state import state


class ConfigValidationError(Exception):
    """Raised when config validation is failing."""


class DockerSocketNotFoundError(Exception):
    """Raised if docker.sock file not found."""


class DockerNetworkError(Exception):
    """Raised if getting a list of networks fails."""


def reraise_if_debug(exc_info: Exception) -> None:
    """Re-raise the active exception if debug mode is enabled, otherwise exit with code 1.

    Must be called from within an ``except`` block: the debug path uses a bare ``raise`` and
    therefore re-raises the currently handled exception, not necessarily ``exc_info``.
    """
    if state.debug:
        raise

    raise typer.Exit(1) from exc_info
