from pathlib import Path

import typer

from deepfellow.common.config import load_config

from .configure import app as configure_app
from .env_command import app as env_app
from .install import app as install_app
from .login import app as login_app
from .start import app as start_app
from .stop import app as stop_app

DEFAULT_CONFIG = Path("~/.deepfellow/server/config.json").expanduser()

app = typer.Typer()


@app.callback()
def callback(
    ctx: typer.Context,
    config: Path = typer.Option(
        DEFAULT_CONFIG, "--config", "-c", envvar="DF_SERVER_CONFIG", help="Path to the config file."
    ),
) -> None:
    """Infra common for all commands.

    This method is run before any server subcommand.

    Args:
        ctx (typer.Context): Typer context
        config (Path, optional): Path to the config file. Defaults to ~/.deepfellow/server/config.json
    """
    ctx.ensure_object(dict)
    ctx.obj["config-path"] = config
    ctx.obj["config"] = load_config()


app.add_typer(install_app)
app.add_typer(configure_app)
app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(env_app, name="env")
app.add_typer(login_app)
