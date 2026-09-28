# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

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
