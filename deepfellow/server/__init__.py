from pathlib import Path

import typer

from .configure import app as configure_app
from .install import app as install_app
from .start import app as start_app

DEFAULT_CONFIG = Path("~/.deepfellow/config-server.yaml").expanduser()

app = typer.Typer()


@app.callback()
def callback(
    ctx: typer.Context,
    config: Path = typer.Option(
        DEFAULT_CONFIG, "--config", "-c", envvar="DF_SERVER_CONFIG", help="Path to the config file."
    ),
) -> None:
    """Infra common for all commands."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


app.add_typer(install_app)
app.add_typer(configure_app)
app.add_typer(start_app)
