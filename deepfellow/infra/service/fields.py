# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra service fields command."""

from typing import Any, cast

import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.rest import make_request
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.connection import call_infra

app = typer.Typer()


def _format_field_options(field: dict[str, Any]) -> str:
    """Format the available options of a ``oneof`` field, e.g. ``available: GPU, CPU``.

    Returns an empty string if the field carries no ``values`` list.
    """
    values = field.get("values") or []
    if not values:
        return ""

    options = [value.get("value", str(value)) if isinstance(value, dict) else str(value) for value in values]
    return f"available: {', '.join(options)}"


def _format_field(field: dict[str, Any]) -> str:
    """Format a single spec field as ``- {name}: {description} (default: {default})``.

    For ``oneof`` fields (those carrying a ``values`` list), the available options are
    appended so the user knows what values may be passed, e.g.
    ``- hardware: Choose hardware: (default: GPU, available: GPU, CPU)``.
    """
    name = field.get("name")
    description = field.get("description")
    default = field.get("default")
    detail = f"default: {default}"

    options = _format_field_options(field)
    if options:
        detail += f", {options}"

    return f"- {name}: {description} ({detail})"


def _format_field_set(field: dict[str, Any]) -> str:
    """Format a single spec field as a ``--set`` usage hint.

    E.g. ``--set hardware=<value>  (optional)  Choose hardware:  (default: GPU, available: GPU, CPU)``.
    """
    name = field.get("name")
    description = field.get("description")
    required = field.get("required", False)
    default = field.get("default")

    required_label = "required" if required else "optional"
    line = f"  --set {name}=<value>  ({required_label})  {description}"

    details = []
    if default is not None:
        details.append(f"default: {default}")
    options = _format_field_options(field)
    if options:
        details.append(options)
    if details:
        line += f"  ({', '.join(details)})"

    return line


@app.command()
def fields(
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
    set_format: bool = typer.Option(False, "--set", help="Display fields as '--set' usage hints"),
    server: str | None = typer.Option(None, callback=validate_server, help="DeepFellow Infra address"),
) -> None:
    """Display configuration fields a service expects."""
    config_file = state.cli_config_file
    config = state.cli_config
    config_external_server = config.get("df_infra_external_url")
    secrets_file = state.cli_secrets_file

    if server is None:
        if config_external_server is not None:
            server = config_external_server
        else:
            server = echo.prompt_until_valid(
                message="Provide DeepFellow Infra URL",
                validation=validate_server,
                error_message="Invalid Deepfellow infra address. Please try again.",
            )

    server = cast("str", server)
    if server != config_external_server:
        env_set(config_file, "DF_INFRA_EXTERNAL_URL", server, should_raise=False)

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    api_key = secrets.get("DF_INFRA_ADMIN_API_KEY")
    if api_key is None:
        api_key = echo.prompt("Provide Infra Admin API Key", password=True)
        env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", api_key, should_raise=False)

    url = f"{server}/admin/services/{name}"
    data = call_infra(
        lambda: make_request(
            method="GET",
            url=url,
            token=api_key,
            err_msg=f"Unable to get fields for service '{name}'.",
            reraise=True,
        ),
        f"Unable to get fields for service '{name}'.",
    )

    service_fields = data.get("spec", {}).get("fields", [])
    if not service_fields:
        echo.info(f"Service '{name}' has no configuration fields.")
        return

    formatter = _format_field_set if set_format else _format_field
    echo.info("\n".join(formatter(field) for field in service_fields))
