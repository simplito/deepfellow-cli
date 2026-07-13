# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect infra dynamic config commands."""

import typer

from .get import app as get_app
from .set import app as set_app

app = typer.Typer()

app.add_typer(get_app)
app.add_typer(set_app)
