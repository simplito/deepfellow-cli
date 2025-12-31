# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Util to perform server-specific docker operations."""

from pathlib import Path

from deepfellow.common.docker import ensure_network, get_docker_network
from deepfellow.common.system import run


def start_server(directory: Path) -> None:
    """Ensure network and start server."""
    ensure_network(get_docker_network(directory))
    run(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory)


def stop_server(directory: Path) -> None:
    """Stop server."""
    run(["docker", "compose", "stop", "server"], cwd=directory)
