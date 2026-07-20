# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra model install command."""

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.model_install import install as install_util

app = typer.Typer()


@app.command()
def install(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    service_name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    model_name: str = typer.Argument(..., help="model name (e.g. llama-3.1-8B)"),
) -> None:
    """Install model."""
    install_util(service_name=service_name, model_name=model_name, server=server)
