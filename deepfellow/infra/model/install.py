# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""infra model install command."""

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.model_install import install as install_util

app = typer.Typer()


@app.command()
def install(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    service_name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    model_name: str = typer.Argument(..., help="model name (e.g. llama-3.1-8B)"),
    spec: str | None = typer.Option(None, help="Model configuration as a JSON object (e.g. '{\"max_concurrent\": 1}')"),
) -> None:
    """Install model."""
    install_util(service_name=service_name, model_name=model_name, server=server, spec=spec)
