"""infra service install command."""

from typing import cast

import httpx
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.rest import post
from deepfellow.common.validation import validate_server

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="service name (e.g. ollama)"),
) -> None:
    """Install service."""
    # Get token for the server
    config_file = ctx.obj.get("cli-config-file")
    config = ctx.obj.get("cli-config")
    config_external_server = config.get("df_infra_external_url")
    secrets_file = ctx.obj.get("cli-secrets-file")
    server = None

    if server is None and config_external_server is not None:
        server = config_external_server

    if server is None and config_external_server is None:
        while server is None:
            try:
                server = echo.prompt(
                    "Provide DeepFellow Infra URL", default=config_external_server, validation=validate_server
                )
            except typer.BadParameter:
                echo.error("Invalid Deepfellow Infra address. Please try again.")

    if server != config_external_server:
        env_set(config_file, "DF_INFRA_EXTERNAL_URL", cast("str", server), should_raise=False)

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    api_key = secrets.get("DF_INFRA_ADMIN_API_KEY")
    if api_key is None:
        api_key = echo.prompt("Provide Infra Admin API Key", password=True)
        env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", api_key, should_raise=False)

    url = f"{server}/admin/services/{name}"

    try:
        data = post(url, api_key, item_name="Service", data={"spec": {}}, reraise=True)
    except httpx.HTTPStatusError as exc:
        msg = "Unable to install service"
        if exc.response:
            msg = exc.response.text

        echo.error(msg)
        raise typer.Exit(1) from exc

    if data.get("status") != "OK":
        echo.error("Unable to install service.")
        raise typer.Exit(1)

    echo.success(f"Service {name} installed.")
