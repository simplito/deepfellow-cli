# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Options for infra."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import typer

from deepfellow.common.defaults import DF_INFRA_DIRECTORY


@dataclass
class ServiceFieldDef:
    """Spec field definition for a cloud service."""

    name: str
    type: Literal["text", "password"]
    required: bool
    description: str
    default: str | None = None


def directory_option(
    help: str = "Directory of the DeepFellow Infra installation.", exists: bool = False, **kwargs: Any
) -> Path:
    """typer.Option wrapper for d option in infra commands.

    Arguments:
        help (str): help message to display in --help
        exists (bool): should we check if directory exists and is readable/writable
        kwargs (Any): kwargs to be passed to typer.Option

    Returns:
        Path of the infra directory
    """
    if exists:
        kwargs |= {
            "exists": True,
            "file_okay": False,  # can't be a file
            "dir_okay": True,  # can be a directory
            "readable": True,
            "writable": True,
            "resolve_path": True,  # convert from symlinks to absolute path
        }

    return typer.Option(
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help=help,
        **kwargs,
    )


CLOUD_SERVICE_SPECS: dict[str, list[ServiceFieldDef]] = {
    "claude": [
        ServiceFieldDef(
            name="api_url", type="text", required=False, description="API URL", default="https://api.anthropic.com"
        ),
        ServiceFieldDef(name="api_key", type="password", required=True, description="API Key"),
        ServiceFieldDef(
            name="anthropic_version",
            type="text",
            required=True,
            description="Anthropic API Version",
            default="2023-06-01",
        ),
        ServiceFieldDef(name="anthropic_beta", type="text", required=False, description="Anthropic Beta Header"),
    ],
    "google": [
        ServiceFieldDef(
            name="api_url",
            type="text",
            required=False,
            description="API URL",
            default="https://generativelanguage.googleapis.com",
        ),
        ServiceFieldDef(name="api_key", type="password", required=False, description="API Key", default=""),
    ],
    "openai": [
        ServiceFieldDef(
            name="api_url", type="text", required=False, description="API URL", default="https://api.openai.com"
        ),
        ServiceFieldDef(name="api_key", type="password", required=False, description="API Key", default=""),
    ],
    "sindri": [
        ServiceFieldDef(
            name="api_url",
            type="text",
            required=False,
            description="API URL",
            default="https://sindri.app/api/ai/v1/openai",
        ),
        ServiceFieldDef(name="api_key", type="password", required=True, description="API Key"),
    ],
}
