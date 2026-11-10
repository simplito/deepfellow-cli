# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Docker helpers for workspace commands."""

from pathlib import Path

import typer

from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_WORKSPACE_PORT,
    SERVER_CONTAINER_NAME,
    WORKSPACE_APP_SERVICE,
)
from deepfellow.common.docker import DockerError, ensure_network, is_service_running_or_raise, local_url
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.common.system import run
from deepfellow.workspace.utils.install import BIND_ADDRESS_KEY, DOCKER_NETWORK_KEY, PORT_KEY, read_existing_env
from deepfellow.workspace.utils.server import is_server_reachable


def is_server_container_running() -> bool:
    """Check whether the DeepFellow Server container is running on this host.

    Returns:
        True when a running container named `server` exists; False otherwise, also when Docker cannot tell.
    """
    try:
        result = run(
            ["docker", "ps", "--filter", f"name=^{SERVER_CONTAINER_NAME}$", "--filter", "status=running", "-q"],
            capture_output=True,
            raises=DockerError,
        )
    except DockerError:
        return False
    return bool(result and result.strip())


def is_server_running(directory: Path) -> bool:
    """Check whether the DeepFellow Server this Workspace uses is up.

    The Server may run on this host (a `server` container) or elsewhere (`DF_SERVER_URL` of the Workspace's .env),
    so either one being up counts.

    Args:
        directory: Workspace install directory.

    Returns:
        True when the local Server container runs or the Server URL answers.
    """
    if is_server_container_running():
        return True
    server_url = read_existing_env(directory).get("DF_SERVER_URL")
    return bool(server_url) and is_server_reachable(str(server_url))


def confirm_server_running(directory: Path) -> None:
    """Make sure DeepFellow Server is running, or that the user agrees to go on without it.

    Workspace needs DeepFellow Server; when it is not running the user is asked whether to go on.

    Args:
        directory: Workspace install directory.

    Raises:
        typer.Exit: When the user declines to go on without DeepFellow Server.
    """
    if not is_server_running(directory) and not echo.confirm(
        "DeepFellow Server is not running, and Workspace needs it. Start Workspace anyway?"
    ):
        echo.info("Start DeepFellow Server first with 'server start'.")
        raise typer.Exit(1)


def start_workspace(directory: Path) -> None:
    """Start the Workspace stack and wait until its services are healthy.

    The Docker network shared with DeepFellow Server is created when missing, since compose declares it external.
    Mongo and Redis of the stack are awaited through their healthchecks in compose.

    Args:
        directory: Workspace install directory.

    Raises:
        typer.Exit: When the network cannot be created or the stack fails to start.
    """
    echo.info("Starting DeepFellow Workspace.")
    network = read_existing_env(directory).get(DOCKER_NETWORK_KEY) or DF_INFRA_DOCKER_NETWORK
    try:
        ensure_network(network)
        run(["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory, raises=DockerError)
    except DockerNetworkError as exc:
        echo.error(f"Could not prepare the Docker network '{network}': {exc}")
        raise typer.Exit(1) from exc
    except DockerError as exc:
        echo.error("Starting DeepFellow Workspace failed; see the Docker output above.")
        raise typer.Exit(1) from exc


def workspace_url(directory: Path) -> str:
    """URL the CLI reaches the Workspace at.

    Args:
        directory: Workspace install directory.

    Returns:
        The URL built from the port and bind address kept in the Workspace's .env.
    """
    env = read_existing_env(directory)
    return local_url(env.get(PORT_KEY) or DF_WORKSPACE_PORT, env.get(BIND_ADDRESS_KEY))


def stop_workspace(directory: Path) -> None:
    """Stop the Workspace containers, keeping them and their data.

    Args:
        directory: Workspace install directory.
    """
    run(["docker", "compose", "stop"], cwd=directory)


def workspace_running(directory: Path) -> bool | None:
    """Tell whether the Workspace app container is running.

    Args:
        directory: Workspace install directory.

    Returns:
        Whether it runs, or `None` when Docker cannot be asked.
    """
    try:
        return is_service_running_or_raise(WORKSPACE_APP_SERVICE, directory)
    except DockerError:
        return None


def offer_restart(directory: Path, change: str, no_restart: bool = False) -> None:
    """Restart a running Workspace when the user agrees, so a change of its configuration applies.

    A stopped Workspace is left stopped, since the change applies on its next start.

    Args:
        directory: Workspace install directory.
        change: What is applied, for the messages (e.g. "change", "update").
        no_restart: Do not restart; only tell how to apply the change.
    """
    running = workspace_running(directory)
    if running is None:
        echo.warning(
            f"Could not check whether DeepFellow Workspace is running; run 'workspace restart' to apply the {change}."
        )
        return
    if not running:
        echo.info(f"DeepFellow Workspace is not running; the {change} applies on the next 'workspace start'.")
        return
    if no_restart or not echo.confirm(f"Restart DeepFellow Workspace now to apply the {change}?", default=True):
        echo.info(f"Run 'workspace restart' to apply the {change}.")
        return
    confirm_server_running(directory)
    stop_workspace(directory)
    start_workspace(directory)
    echo.info(f"DeepFellow Workspace restarted on {workspace_url(directory)}")
