# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect server toolbox commands."""

import typer

from .create import app as create_app
from .delete import app as delete_app
from .get import app as get_app
from .list import app as list_app
from .update import app as update_app

app = typer.Typer(no_args_is_help=True)

app.add_typer(get_app)
app.add_typer(list_app)
app.add_typer(create_app)
app.add_typer(update_app)
app.add_typer(delete_app)
