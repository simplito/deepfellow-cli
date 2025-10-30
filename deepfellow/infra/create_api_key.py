"""Create API Key typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def create_api_key() -> None:
    """Create API Key DeepFellow Infra."""
    config = get_config_path()
    typer.echo(f"DeepFellow Infra create-api-key using config: {config}")
    echo.info("Creating API Key for DeepFellow Infra")
