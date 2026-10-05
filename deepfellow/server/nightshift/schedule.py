# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift schedule typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import NightshiftModeChoice
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.validation import validate_hhmm
from deepfellow.server.utils.nightshift import apply_nightshift_schedule
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def schedule(
    start: str | None = typer.Option(
        None, callback=validate_hhmm, help="Start hour (HH:MM, host timezone). Omit to keep the current value."
    ),
    stop: str | None = typer.Option(
        None, callback=validate_hhmm, help="Stop hour (HH:MM, host timezone). Omit to keep the current value."
    ),
    directory: Path = directory_option(exists=True),
) -> None:
    """Change the Nightshift worker's shift-mode schedule.

    Only applies when Nightshift is already in `shift` mode - see `server nightshift mode`.
    Pass just the hour you want to change; the other keeps its current value, so changing only the
    stop hour doesn't require re-typing a start hour you're not actually changing.
    """
    check_server_directory(directory)
    assert_docker()

    if start is None and stop is None:
        echo.info("Nothing to change - pass --start and/or --stop.")
        return

    env_content = read_env_file_to_dict(directory / ".env")
    mode = str(env_content.get("df_nightshift_mode", NightshiftModeChoice.always.value))
    if mode != NightshiftModeChoice.shift.value:
        echo.error("A schedule only applies in 'shift' mode. Run `server nightshift mode shift` first.")
        raise typer.Exit(1)

    resolved_start = start or str(env_content.get("df_nightshift_start", ""))
    resolved_stop = stop or str(env_content.get("df_nightshift_stop", ""))
    if not resolved_start or not resolved_stop:
        echo.error("The current schedule in .env is incomplete - pass both --start and --stop.")
        raise typer.Exit(1)

    apply_nightshift_schedule(
        directory,
        mode,
        resolved_start,
        resolved_stop,
        {"DF_NIGHTSHIFT_START": resolved_start, "DF_NIGHTSHIFT_STOP": resolved_stop},
    )
    echo.success(f"Nightshift schedule updated: start {resolved_start}, stop {resolved_stop}.")
