# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Top-level update command for all DeepFellow components."""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from deepfellow.cli.update import update as update_cli
from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_INFRA_IMAGE,
    DF_SERVER_IMAGE,
    DOCKER_COMPOSE_CONFIG_FILENAME,
)
from deepfellow.common.docker import load_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, translate_to_install_error
from deepfellow.common.state import state
from deepfellow.common.system import run
from deepfellow.infra.update import update as update_infra
from deepfellow.server.update import update as update_server
from deepfellow.server.utils.options import get_default_server_directory

app = typer.Typer()


class UpdateStepsError(Exception):
    """Raised when the infra/server steps run in a new process fail or the process can't be started."""


def _uses_local_image(directory: Path, service: str) -> bool:
    """Return whether `service` in `directory`'s compose file is pinned to a local image.

    A `pull_policy: never` on the service means the user deliberately installed it with
    `--local-image`, pointing it at an image only they built. `update`'s own `local_image=False`
    would otherwise strip that pin and overwrite it with the registry image.
    """
    compose = load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    return compose.get("services", {}).get(service, {}).get("pull_policy") == "never"


def _run_step(step: Callable[[], None]) -> bool:
    """Run one update step, swallowing the InstallError it raises on failure.

    The underlying command has already reported the specific error via echo before raising;
    `translate_to_install_error` catches it (and any other typer/Docker/OSError failure, even
    in `--debug` mode) so a single failing component (e.g. Docker not running for Infra) can't
    abort the rest of `update`. Returns whether the step succeeded.
    """
    try:
        translate_to_install_error(step)()
    except InstallError as exc:
        echo.error(str(exc))
        return False
    return True


def _update_components() -> bool:
    """Update Infra and Server in this process; return whether every attempted step succeeded."""
    ok = True
    if DF_INFRA_DIRECTORY.is_dir():
        if _uses_local_image(DF_INFRA_DIRECTORY, "infra"):
            echo.info("DeepFellow Infra uses a locally built image, skipping.")
        else:
            ok = _run_step(
                lambda: update_infra(directory=DF_INFRA_DIRECTORY, image=DF_INFRA_IMAGE, local_image=False, tag=None)
            )
    else:
        echo.info("DeepFellow Infra not installed, skipping.")

    # This command has no Nightshift options, so when unattended (non-interactive without `--yes`)
    # it skips adding Nightshift to a server install without it - `server update` then warns.
    nightshift = False if state.non_interactive and not state.yes else None
    server_directory = get_default_server_directory()
    if server_directory.is_dir():
        if _uses_local_image(server_directory, "server"):
            echo.info("DeepFellow Server uses a locally built image, skipping.")
        else:
            ok = (
                _run_step(
                    lambda: update_server(
                        directory=server_directory,
                        image=DF_SERVER_IMAGE,
                        local_image=False,
                        tag=None,
                        nightshift=nightshift,
                        rabbitmq_url=None,
                        rabbitmq_username="",
                        rabbitmq_password="",
                    )
                )
                and ok
            )
    else:
        echo.info("DeepFellow Server not installed, skipping.")

    return ok


def _global_flags() -> list[str]:
    """Return this invocation's global options, to be placed before the subcommand of a new `deepfellow` process."""
    flags = []
    if state.debug:
        flags.append("--debug")
    if state.yes:
        flags.append("--yes")
    if state.non_interactive:
        flags.append("--non-interactive")
    flags.extend(["--config", str(state.cli_config_file), "--secrets", str(state.cli_secrets_file)])
    return flags


def _update_components_in_new_process(executable: str) -> bool:
    """Run `deepfellow update --skip-cli` as a new process; return whether every step succeeded.

    The process inherits the terminal (nothing is captured), so its prompts and errors show as usual.
    When it can't be started at all, the steps run in this process instead, with the previous CLI version.
    """
    try:
        run([executable, *_global_flags(), "update", "--skip-cli"], raises=UpdateStepsError)
    except UpdateStepsError as exc:
        # `run()` chains the original failure: an OSError means the process never started.
        if isinstance(exc.__cause__, OSError):
            echo.warning(
                f"Couldn't run the updated CLI ({executable}: {exc}) - "
                "updating Infra and Server with the previous CLI version."
            )
            return _update_components()
        echo.error(
            f"Updating Infra and Server with the updated CLI ({executable}) failed, see the output above. "
            "Retry with `deepfellow update --skip-cli`."
        )
        return False
    return True


@app.command()
def update(
    skip_cli: Annotated[
        bool, typer.Option("--skip-cli", hidden=True, help="Skip the CLI update and only update Infra and Server.")
    ] = False,
) -> None:
    """Update DeepFellow CLI, Infra, and Server.

    The CLI is always updated. Infra and Server are updated only if installed locally
    (their directory exists); a missing component is skipped rather than treated as an
    error. A component pinned to a locally built image (`pull_policy: never`, set by its
    own `--local-image` install/update) is also skipped, rather than overwritten with the
    registry image. If any attempted step fails, `update` exits with a non-zero status
    after still attempting the remaining steps.
    """
    # Modules imported by this process stay at the version from before the CLI updated itself,
    # so after a successful CLI update the Infra and Server steps run in a new `deepfellow`
    # process (`update --skip-cli`) with the updated code. They run in this process when the CLI
    # update failed or the `deepfellow` executable can't be found or started.
    if skip_cli:
        if not _update_components():
            raise typer.Exit(1)
        return

    cli_ok = _run_step(update_cli)
    executable = shutil.which("deepfellow") if cli_ok else None
    if executable is not None:
        echo.debug(f"Running the Infra and Server update with the updated CLI: {executable}")
        ok = _update_components_in_new_process(executable)
    else:
        if cli_ok:
            echo.warning(
                "The updated `deepfellow` isn't on PATH - updating Infra and Server with the previous CLI version."
            )
        ok = _update_components() and cli_ok

    if not ok:
        raise typer.Exit(1)
