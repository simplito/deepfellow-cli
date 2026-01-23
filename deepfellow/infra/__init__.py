# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect infra commands."""

import typer

from .connect import app as connect_app
from .disconnect import app as disconnect_app
from .env_command import app as env_app
from .env_command.info import app as info_app
from .install import app as install_app
from .logs import app as logs_app
from .model import app as model_app
from .service import app as service_app
from .ssl_on import app as ssl_on_app
from .start import app as start_app
from .status import app as status_app
from .stop import app as stop_app
from .uninstall import app as uninstall_app
from .update import app as update_app

app = typer.Typer()


app.add_typer(info_app)
app.add_typer(install_app)
app.add_typer(uninstall_app)
app.add_typer(start_app)
app.add_typer(status_app)
app.add_typer(stop_app)
app.add_typer(update_app)
app.add_typer(ssl_on_app)
app.add_typer(connect_app)
app.add_typer(disconnect_app)
app.add_typer(env_app, name="env", help="Manage Infra environment variables.")
app.add_typer(service_app, name="service", help="Manage DeepFellow Infra services.")
app.add_typer(model_app, name="model", help="Manage DeepFellow Infra models.")
app.add_typer(logs_app)
