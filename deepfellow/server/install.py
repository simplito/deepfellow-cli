"""Install server typer command."""

import shutil
from pathlib import Path

import typer

from deepfellow.common.defaults import DF_SERVER_DIRECTORY, DF_SERVER_REPO
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.git import Git
from deepfellow.common.system import run

app = typer.Typer()


@app.command()
def install(
    ctx: typer.Context,
    branch: str | None = typer.Option(None, help="Specify a branch to install from"),
    tag: str | None = typer.Option(None, help="Specify a tag to install from"),
    directory: Path = typer.Option(
        DF_SERVER_DIRECTORY, envvar="DF_SERVER_DIRECTORY", help="Target directory for the server installation."
    ),
    repository: str = typer.Option(DF_SERVER_REPO, envvar="DF_SERVER_REPO", help="Git repository of server."),
) -> None:
    """Install server."""
    debug = ctx.obj.get("debug", False)
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{repository=}\n{branch=},\n{tag=},\n{directory=},\n{yes=}")
    omit_pulling_repository = False
    if directory.is_dir():
        echo.warning(f"Directory {directory} already exists.")
        omit_pulling_repository = typer.confirm("Should I proceed installation with the existing code?")
        if not omit_pulling_repository:
            raise typer.Exit(1)

    if (
        not omit_pulling_repository  # We already asked the question about installation
        and not yes  # auto-confirm mode is on
        and not typer.confirm(f"Confirm installing DF Server in {directory}", default=True)
    ):
        raise typer.Exit(1)

    echo.info("Installing DF Server.")
    if not omit_pulling_repository:
        try:
            directory.mkdir(parents=True)
        except Exception as exc_info:
            echo.error("Unable to create infra directory.")
            reraise_if_debug(exc_info)

        echo.info("Cloning repository...")
        git = Git(repository=repository)
        git.clone(branch=branch, tag=tag, directory=directory)

    # Install dependencies
    echo.info("Installing dependencies...")
    command = "uv sync"
    if not debug:
        command += " --quiet"

    run(command, cwd=directory)

    # Configuration
    # TODO Ask a few questions anf fill in the secret details
    env_file = directory / ".env"
    shutil.copy(directory / "example.env", env_file)

    echo.success("DF Server installed.")
    echo.info(
        f"Configuration file:\n{env_file}\n"
        "Edit to provide the appropriate values for your installation and continue with:\n"
        "`deepfellow server install-continue`"
    )
    echo.debug("TODO Can we edit the Infra config?")
