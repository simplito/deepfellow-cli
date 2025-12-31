# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Util to perform infra-specific docker operations."""

from pathlib import Path

from deepfellow.common.docker import ensure_network, get_docker_network
from deepfellow.common.system import run


def start_infra(directory: Path) -> None:
    """Ensure network and start infra."""
    ensure_network(get_docker_network(directory))
    run(["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory)


def stop_infra(directory: Path) -> None:
    """Stop infra."""
    run(["docker", "compose", "stop", "infra"], cwd=directory)
