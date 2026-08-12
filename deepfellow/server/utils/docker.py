# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Util to perform server-specific docker operations."""

from pathlib import Path
from typing import NoReturn

from deepfellow.common.docker import (
    DockerError,
    ensure_network,
    get_docker_network,
    resolve_compose_volume_name,
    volume_exists,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.system import run

MONGO_AUTH_FAILURE_SIGNATURES = ("OperationFailure", "Authentication failed")


def start_server(directory: Path) -> None:
    """Ensure network and start server."""
    ensure_network(get_docker_network(directory))
    try:
        run(["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory, raises=DockerError)
    except DockerError as exc:
        _handle_start_failure(directory, exc)


def _handle_start_failure(directory: Path, exc: DockerError) -> NoReturn:
    """Report why the server stack failed to start, detecting a known Mongo credential mismatch.

    A stale ``mongo`` Docker volume from a previous install can hold root credentials that no
    longer match the current ``.env`` (e.g. after ``server uninstall``, which removes ``.env`` but
    not the volume, followed by a fresh ``server install``). That specific case surfaces as a
    generic "container server is unhealthy" from ``docker compose up`` with no indication of the
    real cause, so it's worth grepping the server logs for the underlying pymongo auth error.

    Always exits: ``--debug`` re-raises ``exc`` with its traceback, otherwise ``typer.Exit(1)``.
    """
    try:
        logs = run(
            ["docker", "compose", "logs", "--tail", "200", "server"],
            cwd=directory,
            capture_output=True,
            raises=DockerError,
        )
    except DockerError as logs_exc:
        echo.debug(logs_exc)
        logs = None

    if logs and all(signature in logs for signature in MONGO_AUTH_FAILURE_SIGNATURES):
        volume_name = resolve_compose_volume_name(directory, "mongo")
        if volume_name and volume_exists(volume_name):
            # Only blame the locally-managed volume once we've confirmed it actually exists -
            # a custom/external MongoDB (--mongodb-url) has no such volume at all, and a
            # confidently-worded `docker volume rm` suggestion for a volume that was never
            # created would be actively misleading.
            echo.error(
                f"DeepFellow Server failed to authenticate against MongoDB. The 'mongo' Docker volume "
                f"('{volume_name}') likely already holds credentials that no longer match .env (e.g. "
                "after 'server uninstall' followed by a fresh 'server install'). Restore the original "
                f"Mongo credentials in .env, or remove it with `docker volume rm {volume_name}`, then "
                "retry."
            )
        else:
            echo.error(
                "DeepFellow Server failed to authenticate against MongoDB. Check the DF_MONGO_* "
                "credentials in .env against the MongoDB instance they connect to."
            )
    elif not exc.args or exc.args[0] in (None, ""):
        # docker compose up's own output streams straight to the terminal (never captured), so
        # a plain DockerError from it carries no stderr of its own to show here.
        echo.error("Failed to start DeepFellow Server. See the Docker output above for details.")
    else:
        echo.error(f"Failed to start DeepFellow Server: {exc}")
    reraise_if_debug(exc)


def stop_server(directory: Path) -> None:
    """Stop server."""
    run(["docker", "compose", "stop", "server"], cwd=directory)
