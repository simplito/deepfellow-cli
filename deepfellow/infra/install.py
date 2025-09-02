"""Install infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import save_env_file
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
        override_existing_installation = typer.confirm("Should I override existing installation?")
        if not override_existing_installation:
            raise typer.Exit(1)

    echo.info("Installing DF Infra.")
    if not directory_exists:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create infra directory.")
            reraise_if_debug(exc_info)

    infra_values = {"DF_INFRA_PORT": port, "DF_INFRA_IMAGE": image}
    save_env_file(directory / ".env", infra_values)
    save_compose_file({"services": COMPOSE_INFRA}, directory / "docker-compose.yml")
    echo.success("DF Infra installed.\nCall `depfellow infra start`.")
