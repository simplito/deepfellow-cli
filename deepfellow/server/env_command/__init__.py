# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect infra env commands."""

import typer

from .info import app as info_app
from .set import app as set_app

app = typer.Typer()


app.add_typer(set_app)
app.add_typer(info_app)
