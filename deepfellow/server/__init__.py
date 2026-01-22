# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import typer

from .create_admin import app as create_admin_app
from .env_command import app as env_app
from .env_command.info import app as info_app
from .install import app as install_app
from .login import app as login_app
from .logs import app as logs_app
from .opentelemetry import app as opentelemetry_app
from .organization import app as organization_app
from .password_reset import app as reset_password_app
from .project import app as project_app
from .start import app as start_app
from .status import app as status_app
from .stop import app as stop_app
from .update import app as update_app

app = typer.Typer()

app.add_typer(info_app)
app.add_typer(install_app)
app.add_typer(create_admin_app)
app.add_typer(opentelemetry_app)
app.add_typer(reset_password_app)
app.add_typer(start_app)
app.add_typer(status_app)
app.add_typer(stop_app)
app.add_typer(update_app)
app.add_typer(logs_app)
app.add_typer(env_app, name="env", help="Manage DeepFellow Server environment variables.")
app.add_typer(login_app)
app.add_typer(organization_app, name="organization", help="Manage Organizations.")
app.add_typer(project_app, name="project", help="Manage Projects.")
