"""Collect infra commands."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.exceptions import ConfigValidationError

from .create_api_key import app as create_api_key_app
from .download import app as download_app
from .env_command import app as env_app
from .install import app as install_app
from .models import app as models_app
from .start import app as start_app
from .stop import app as stop_app
from .utils.validation import validate_config

app = typer.Typer()


@app.callback()
def callback(
    ctx: typer.Context,
) -> None:
    """Infra common for all commands.

    This method is run before any infra subcommand.
    """
    # validate config
    config = ctx.obj.get("infra-config", {})
    if ctx.invoked_subcommand not in ("configure", "install", "start", "stop", "env"):
        try:
            validate_config(config)
        except ConfigValidationError as err:
            echo.error(str(err))
            raise typer.Exit(1) from err


app.add_typer(install_app)
app.add_typer(models_app)
app.add_typer(download_app)
app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(create_api_key_app)
app.add_typer(env_app, name="env")
