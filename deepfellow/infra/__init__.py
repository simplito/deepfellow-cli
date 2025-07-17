from pathlib import Path

import typer

from .create_api_key import app as create_api_key_app
from .download import app as download_app
from .install import app as install_app
from .models import app as models_app
from .start import app as start_app

app = typer.Typer()

DEFAULT_CONFIG = Path("~/.deepfellow/infra/config.json").expanduser()


@app.callback()
def callback(
    ctx: typer.Context,
    config: Path = typer.Option(
        DEFAULT_CONFIG, "--config", "-c", envvar="DF_INFRA_CONFIG", help="Path to the config file."
    ),
) -> None:
    """Infra common for all commands."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


app.add_typer(install_app)
app.add_typer(models_app)
app.add_typer(download_app)
app.add_typer(start_app)
app.add_typer(create_api_key_app)
