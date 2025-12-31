# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect server organization commands."""

import typer

from .admin_api_key import app as admin_api_key_app
from .create import app as create_app
from .get import app as get_app
from .list import app as list_app

app = typer.Typer()


app.add_typer(create_app)
app.add_typer(list_app)
app.add_typer(get_app)
app.add_typer(admin_api_key_app, name="api-key", help="Manage Organization API Keys.")
# Temporarily disabling the delete organization.
# from .delete import app as delete_app
# app.add_typer(delete_app)
