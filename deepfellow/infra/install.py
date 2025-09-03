"""Install infra typer command."""

from pathlib import Path
from typing import Any

import typer
from deepfellow.common.config import configure_uuid_key, env_to_dict, read_env_file, save_env_file
from deepfellow.common.defaults import DF_INFRA_DIRECTORY, DF_INFRA_IMAGE
from deepfellow.common.docker import COMPOSE_INFRA, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    directory: Path = typer.Option(
        DF_INFRA_DIRECTORY,
        "--directory",
        "--dir",
        envvar="DF_INFRA_DIRECTORY",
        help="Target directory for the Infra installation.",
    ),
    port: int = typer.Option(8080, envvar="DF_INFRA_PORT", help="Port to use to serve the Infra from."),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="Infra docker image."),
) -> None:
    """Install infra with docker."""
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{directory=},\n{yes=}")
    override_existing_installation = False
    directory_exists = False
    if directory.is_dir():
        directory_exists = True
        echo.warning(f"Directory {directory} already exists.")
        override_existing_installation = echo.confirm("Should I override existing installation?")
        if not override_existing_installation:
            raise typer.Exit(1)

    echo.info("Installing DF Infra.")
    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create infra directory.")
            reraise_if_debug(exc_info)

    env_file = directory / ".env"
    original_env_content: dict[str, Any] = {}
    if env_file.exists():
        original_env_vars = read_env_file(env_file)
        original_env_content = env_to_dict(original_env_vars)

    echo.info("A DF Server or other infra needs to identify in DF Infra by providing an API Key.")
    api_key = configure_uuid_key("API Key", original_env_content.get("df_infra_api_key"))

    echo.info("An Admin needs to identify itself in DF Infra to perform actions.")
    admin_api_key = configure_uuid_key("Admin API Key", original_env_content.get("df_infra_admin_api_key"))

    infra_values = {
        "DF_INFRA_PORT": port,
        "DF_INFRA_IMAGE": image,
        "DF_INFRA_API_KEY": api_key,
        "DF_INFRA_ADMIN_API_KEY": admin_api_key,
    }
    save_env_file(directory / ".env", infra_values)
    save_compose_file({"services": COMPOSE_INFRA}, directory / "docker-compose.yml")
    echo.success("DF Infra installed.\nCall `depfellow infra start`.")
