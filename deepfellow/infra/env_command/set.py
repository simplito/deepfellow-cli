"""infra env set command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def set(
    directory: Path = directory_option("Directory of the Infra installation."),
    env_name: str = typer.Argument(..., help="Name of the environment variable", callback=lambda x: x.upper()),
    env_value: str = typer.Argument("", help="Value of the environment variable"),
    df_prefix: bool = typer.Option(True, help="Add DF_ prefix if not provided?"),
) -> None:
    """Set environment configuration."""
    env_file = directory / ".env"
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)

    if df_prefix and not env_name.startswith("DF_"):
        echo.info("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    envs[env_name] = env_value
    save_env_file(env_file, envs)
