"""Collect infra commands."""

import typer

from .env_command import app as env_app
from .env_command.info import app as info_app
from .install import app as install_app
from .model import app as model_app
from .service import app as service_app
from .start import app as start_app
from .stop import app as stop_app

# from deepfellow.common.echo import echo
# from deepfellow.common.exceptions import ConfigValidationError
# from .create_api_key import app as create_api_key_app
# from .utils.validation import validate_config
# from .download import app as download_app
# from .models import app as models_app

app = typer.Typer()


@app.callback()
def callback(
    ctx: typer.Context,
) -> None:
    """DeepFellow Infra commands.
    \f
    This method is run before any infra subcommand.
    """
    # Switched off validating config until we will have the actual config
    # validate config
    # config = ctx.obj.get("infra-config", {})
    # if ctx.invoked_subcommand not in ("configure", "install", "start", "stop", "env"):
    #     try:
    #         validate_config(config)
    #     except ConfigValidationError as err:
    #         echo.error(str(err))
    #         raise typer.Exit(1) from err


app.add_typer(info_app)
app.add_typer(install_app)
# app.add_typer(models_app)
# app.add_typer(download_app)
app.add_typer(start_app)
app.add_typer(stop_app)
# app.add_typer(create_api_key_app)
app.add_typer(env_app, name="env", help="Manage Infra environment variables.")
app.add_typer(service_app, name="service", help="Manage DeepFellow Infra services.")
app.add_typer(model_app, name="model", help="Manage DeepFellow Infra models.")
