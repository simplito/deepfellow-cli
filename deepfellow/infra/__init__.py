"""Collect infra commands."""

import typer

from .env_command import app as env_app
from .env_command.info import app as info_app
from .install import app as install_app
from .model import app as model_app
from .service import app as service_app
from .ssl_on import app as ssl_on_app
from .start import app as start_app
from .stop import app as stop_app

app = typer.Typer()


app.add_typer(info_app)
app.add_typer(install_app)
app.add_typer(start_app)
app.add_typer(stop_app)
app.add_typer(ssl_on_app)
app.add_typer(env_app, name="env", help="Manage Infra environment variables.")
app.add_typer(service_app, name="service", help="Manage DeepFellow Infra services.")
app.add_typer(model_app, name="model", help="Manage DeepFellow Infra models.")
