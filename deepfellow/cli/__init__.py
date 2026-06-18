# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect cli commands."""

import typer

from .uninstall import app as uninstall_app
from .update import app as update_app

app = typer.Typer()

app.add_typer(uninstall_app)
app.add_typer(update_app)
