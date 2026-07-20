# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service install command."""

from typing import Annotated

import typer

from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.service_install import install as install_util

app = typer.Typer()


@app.command()
def install(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Infra address"),
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    service_api_key: str | None = typer.Option(None, "--api-key", help="API key for remote services (e.g. claude)"),
    spec: str | None = typer.Option(
        None, help='Service configuration as a JSON object (e.g. \'{"url": "http://host:11434"}\')'
    ),
    set_args: Annotated[
        list[str] | None, typer.Option("--set", help="Set a service field (e.g. --set hardware=GPU)")
    ] = None,
    prompt_all: Annotated[bool, typer.Option(help="Prompt for all fields including optional ones")] = True,
) -> None:
    """Install service."""
    install_util(
        name=name,
        server=server,
        service_api_key=service_api_key,
        spec=spec,
        set_args=set_args,
        prompt_all=prompt_all,
    )
