# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift mode typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import NightshiftModeChoice
from deepfellow.common.echo import echo
from deepfellow.common.install import assert_docker
from deepfellow.common.validation import validate_hhmm
from deepfellow.server.utils.nightshift import apply_nightshift_schedule, validate_nightshift_schedule
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.systemd import assert_systemd_available
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


@app.command()
def mode(
    mode: NightshiftModeChoice = typer.Argument(..., help="Nightshift operating mode."),
    start: str | None = typer.Option(
        None,
        callback=validate_hhmm,
        help="Start hour (HH:MM, host timezone). Only used with 'shift'. Defaults to the current value, else 22:00.",
    ),
    stop: str | None = typer.Option(
        None,
        callback=validate_hhmm,
        help="Stop hour (HH:MM, host timezone). Only used with 'shift'. Defaults to the current value, else 06:00.",
    ),
    directory: Path = directory_option(exists=True),
) -> None:
    """Change the Nightshift worker's operating mode without reinstalling.

    Switching to `shift` creates user-level systemd timers that start/stop the worker container at
    the given hours (RabbitMQ and the server keep running continuously). Switching to `always`
    removes any existing timers - the worker then runs continuously like the rest of the stack.
    """
    check_server_directory(directory)
    assert_docker()

    env_content = read_env_file_to_dict(directory / ".env")
    start = start or str(env_content.get("df_nightshift_start") or "22:00")
    stop = stop or str(env_content.get("df_nightshift_stop") or "06:00")
    validate_nightshift_schedule(mode.value, start, stop)

    env_updates = {"DF_NIGHTSHIFT_MODE": mode.value}
    if mode == NightshiftModeChoice.shift:
        # Fail fast, before printing anything else, if this host could never support shift mode
        # at all - rather than warning about RabbitMQ behavior and then limping through a doomed
        # `loginctl`/sudo dance while creating the timers.
        assert_systemd_available()
        echo.warning(
            "In shift mode, tasks queued outside the worker's active hours wait in RabbitMQ until "
            "its next scheduled start."
        )
        env_updates |= {"DF_NIGHTSHIFT_START": start, "DF_NIGHTSHIFT_STOP": stop}

    apply_nightshift_schedule(directory, mode.value, start, stop, env_updates)
    echo.success(f"Nightshift mode set to '{mode.value}'.")
