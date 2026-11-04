# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Uninstall server typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict, save_env_file
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.state import state
from deepfellow.common.system import rmtree, run
from deepfellow.server.utils.options import directory_option, get_default_server_directory, set_default_server_directory
from deepfellow.server.utils.systemd import remove_nightshift_timers
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


def _clear_stored_server_url(server_url: str | None) -> None:
    """Remove the CLI's default Server URL if it points at the uninstalled server.

    `server install` stores the local server's URL in the CLI config; left behind, it would make
    Server API commands call a server that no longer exists. Removed rather than emptied, so the
    next `server install` or URL prompt stores a fresh one without asking.

    Args:
        server_url: `DF_SERVER_URL` of the uninstalled server, as read from its `.env`.
    """
    if not server_url or state.cli_config.get("df_server_url") != server_url:
        return
    try:
        save_env_file(state.cli_config_file, {}, docker_note=False, quiet=True, remove=("DF_SERVER_URL",))
    except OSError as exc:
        echo.warning(
            f"Server removed, but could not clear DF_SERVER_URL from {state.cli_config_file}: {exc}. Edit it manually."
        )
        return
    state.cli_config.pop("df_server_url", None)


@app.command()
def uninstall(
    directory: Path = directory_option("DeepFellow Server directory."),
) -> None:
    """Uninstall DeepFellow Server."""
    echo.info("Uninstalling DeepFellow Server.")
    check_server_directory(directory)
    assert_docker()

    echo.info("Turning off DeepFellow Server.")
    run(["docker", "compose", "rm", "-s", "-f"], directory, quiet=True)

    echo.info("Removing Nightshift systemd timers, if any.")
    remove_nightshift_timers(directory)

    server_url = read_env_file_to_dict(directory / ".env").get("df_server_url")

    echo.info("Removing DeepFellow Server files.")
    rmtree(directory)

    _clear_stored_server_url(server_url if isinstance(server_url, str) else None)

    old_default_server_dir = get_default_server_directory()

    if old_default_server_dir.resolve() == directory.resolve():
        set_default_server_directory("", True)

    echo.success("DeepFellow Server uninstalled.")
