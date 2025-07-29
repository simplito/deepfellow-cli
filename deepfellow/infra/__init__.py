from pathlib import Path

import typer

from deepfellow.common.config import load_config
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import ConfigValidationError

from .create_api_key import app as create_api_key_app
from .download import app as download_app
from .install import app as install_app
from .models import app as models_app
from .start import app as start_app
from .utils.validation import validate_config

app = typer.Typer()

DF_INFRA_CONFIG_PATH = Path("~/.deepfellow/infra/config.json").expanduser()


@app.callback()
def callback(
    ctx: typer.Context,
    config: Path = typer.Option(
        DF_INFRA_CONFIG_PATH, "--config", "-c", envvar="DF_INFRA_CONFIG", help="Path to the config file."
    ),
) -> None:
    """Infra common for all commands.

    This method is run before any infra subcommand.

    Args:
        config (Path, optional): Path to the config file. Defaults to ~/.deepfellow/infra/config.json
    """
    ctx.ensure_object(dict)
    ctx.obj["config-path"] = config
    ctx.obj["config"] = load_config()

    # validate config
    try:
        validate_config(ctx.obj["config"])
    except ConfigValidationError as err:
        echo.error(str(err))
        raise typer.Exit(1) from err


app.add_typer(install_app)
app.add_typer(models_app)
app.add_typer(download_app)
app.add_typer(start_app)
app.add_typer(create_api_key_app)
