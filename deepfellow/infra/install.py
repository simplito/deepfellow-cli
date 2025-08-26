"""Install infra typer command."""

import shutil
from pathlib import Path

import typer

from deepfellow.common.defaults import DF_INFRA_CONFIG_PATH, DF_INFRA_DIRECTORY, DF_INFRA_IMAGE, DF_INFRA_REPO
from deepfellow.common.docker import COMPOSE_INFRA, generate_env_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.git import Git
from deepfellow.common.system import run

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    directory: Path = typer.Option(
        DF_INFRA_DIRECTORY, "--directory", "--dir", envvar="DF_INFRA_DIRECTORY", help="Target directory for the Infra installation."
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
    generate_env_file(directory / ".env", infra_values)
    save_compose_file(COMPOSE_INFRA, directory / "docker-compose.yml")
    echo.success("DF Infra installed.")


@app.command()
def install_from_repo(
    ctx: typer.Context,
    branch: str | None = typer.Option(None, help="Specify a branch to install from"),
    tag: str | None = typer.Option(None, help="Specify a tag to install from"),
    directory: Path = typer.Option(
        DF_INFRA_DIRECTORY, "--directory", "--dir", envvar="DF_INFRA_DIRECTORY", help="Target directory for the infra installation."
    ),
    repository: str = typer.Option(DF_INFRA_REPO, envvar="DF_INFRA_REPO", help="Git repository of infra."),
    infra_config: Path = typer.Option(
        DF_INFRA_CONFIG_PATH, "--infra-config", envvar="DF_INFRA_CONFIG_PATH", help="Relative path to the config file."
    ),
) -> None:
    """Install infra."""
    debug = ctx.obj.get("debug", False)
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{infra_config=},\n{repository=}\n{branch=},\n{tag=},\n{directory=},\n{yes=}")
    omit_pulling_repository = False
    if directory.is_dir():
        echo.warning(f"Directory {directory} already exists.")
        omit_pulling_repository = typer.confirm("Should I proceed installation with the existing code?")
        if not omit_pulling_repository:
            raise typer.Exit(1)

    if (
        not omit_pulling_repository  # We already asked the question about installation
        and not yes  # auto-confirm mode is on
        and not typer.confirm(f"Confirm installing DF Infra in {directory}", default=True)
    ):
        raise typer.Exit(1)

    echo.info("Installing DF Infra.")
    if not omit_pulling_repository:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create infra directory.")
            reraise_if_debug(exc_info)

        git = Git(repository=repository)
        git.clone(branch=branch, tag=tag, directory=directory, quiet=not debug)

    # Install dependencies
    echo.info("Installing dependencies...")
    shutil.copy(directory / "default.pyproject.toml", directory / "pyproject.toml")
    command = "poetry install"
    if not debug:
        command += " --quiet"

    run(command, cwd=directory)
    shutil.copy(directory / "config/default.infra_config.toml", directory / infra_config)
    echo.success("DF Infra installed.")
    echo.debug("TODO Can we edit the Infra config?")

    # TODO Find out if we need hooks
    # TODO Sould we ask questions ad update infra config?
