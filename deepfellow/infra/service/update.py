# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra service update command."""

from typing import Annotated

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.service_update import update as update_util

app = typer.Typer()


@app.command()
def update(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    image_version: str | None = typer.Option(
        None,
        "--image-version",
        help="Docker image tag (e.g. 0.12.0). Defaults to the newest release; see the versions command",
    ),
    spec: str | None = typer.Option(None, help='Changed settings as a JSON object (e.g. \'{"hardware": "CPU"}\')'),
    set_args: Annotated[
        list[str] | None, typer.Option("--set", help="Change a setting (e.g. --set hardware=CPU)")
    ] = None,
) -> None:
    """Update an installed service: change its settings, such as the Docker image tag, and recreate it."""
    update_util(name=name, server=server, spec=spec, set_args=set_args, image_version=image_version)
