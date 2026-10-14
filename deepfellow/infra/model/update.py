# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra model update command."""

from typing import Annotated

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.model_update import update as update_util

app = typer.Typer()


@app.command()
def update(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    service_name: str = typer.Argument(..., help="service name (e.g. custom)"),
    model_name: str = typer.Argument(..., help="model name (e.g. doc_chunker)"),
    image_version: str | None = typer.Option(
        None,
        "--image-version",
        help="Docker image tag (e.g. v2.4.0). Defaults to the newest release; see the versions command",
    ),
    spec: str | None = typer.Option(None, help="Changed settings as a JSON object (e.g. '{\"max_concurrent\": 4}')"),
    set_args: Annotated[
        list[str] | None, typer.Option("--set", help="Change a setting (e.g. --set max_concurrent=4)")
    ] = None,
) -> None:
    """Update an installed model: change its settings, such as the Docker image tag, and reinstall it."""
    update_util(
        service_name=service_name,
        model_name=model_name,
        server=server,
        spec=spec,
        set_args=set_args,
        image_version=image_version,
    )
