from pathlib import Path

import typer

from deepfellow.common.config import load_config

# from .configure import app as configure_app
from .create_admin import app as create_admin_app
from .env_command import app as env_app
from .env_command.info import app as info_app
from .install import app as install_app
from .login import app as login_app
from .organization import app as organization_app
from .project import app as project_app
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
    """DeepFellow Server commands.
    \f

    This method is run before any server subcommand.

    Args:
        ctx (typer.Context): Typer context
        config (Path, optional): Path to the config file. Defaults to ~/.deepfellow/server/config.json
    """
    ctx.ensure_object(dict)
    ctx.obj["config-path"] = config
    ctx.obj["config"] = load_config()


app.add_typer(info_app)
app.add_typer(install_app)
# app.add_typer(configure_app)
app.add_typer(create_admin_app)
app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(env_app, name="env", help="Manage DeepFellow Server environment variables.")
app.add_typer(login_app)
app.add_typer(organization_app, name="organization", help="Manage Organizations.")
app.add_typer(project_app, name="project", help="Manage Projects.")
