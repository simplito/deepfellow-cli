# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect infra mcp commands."""

import typer

from .add import app as add_app
from .install import app as install_app
from .list import app as list_app
from .remove import app as remove_app
from .uninstall import app as uninstall_app

app = typer.Typer()

app.add_typer(add_app)
app.add_typer(install_app)
app.add_typer(list_app)
app.add_typer(remove_app)
app.add_typer(uninstall_app)
