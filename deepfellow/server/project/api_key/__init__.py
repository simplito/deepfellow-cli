# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Collect server project api-key commands."""

import typer

from .create import app as create_app
from .revoke import app as revoke_app

app = typer.Typer()


app.add_typer(create_app)
app.add_typer(revoke_app)
