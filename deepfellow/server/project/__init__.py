# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect server project commands."""

import typer

from .api_key import app as api_key_app
from .archive import app as archive_app
from .create import app as create_app
from .get import app as get_app
from .list import app as list_app

app = typer.Typer()


app.add_typer(get_app)
app.add_typer(list_app)
app.add_typer(create_app)
app.add_typer(archive_app)
app.add_typer(api_key_app, name="api-key", help="Manage Project API Keys.")
