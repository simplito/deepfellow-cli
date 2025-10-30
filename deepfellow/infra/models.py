"""Models list typer command."""

import typer

from deepfellow.common.config import get_config_path
from deepfellow.common.echo import echo

app = typer.Typer()


@app.command()
def models() -> None:
    """Models list."""
    config = get_config_path()
    echo.warning(f"DeepFellow Infra models using config: {config}")
    echo.info("DeepFellow Infra list models")
