"""infra info command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def info(
    directory: Path = directory_option(),
) -> None:
    """Display environment configuration."""
    env_file = directory / ".env"
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)

    message = f"Variables stored in {env_file}\n"
    for env, value in envs.items():
        message += f"{env}={value}\n"

    echo.info(message)
