import typer

from .create_api_key import app as create_api_key_app
from .download import app as download_app
from .install import app as install_app
from .models import app as models_app
from .start import app as start_app

app = typer.Typer()
app.add_typer(install_app)
app.add_typer(models_app)
app.add_typer(download_app)
app.add_typer(start_app)
app.add_typer(create_api_key_app)
