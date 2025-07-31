"""Install infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.defaults import DF_INFRA_CONFIG_PATH, DF_INFRA_DIRECTORY, DF_INFRA_REPO
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.git import Git

app = typer.Typer()


@app.command()
def install(
    branch: str | None = typer.Option(None, help="Specify a branch to install from"),
    tag: str | None = typer.Option(None, help="Specify a tag to install from"),
    directory: Path = typer.Option(DF_INFRA_DIRECTORY),
    repository: str = typer.Option(DF_INFRA_REPO),
    config: Path = typer.Option(
        DF_INFRA_CONFIG_PATH, "--config", "-c", envvar="DF_INFRA_CONFIG", help="Path to the config file."
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Automatically answer to all questions"),
) -> None:
    """Install infra."""
    config_path = config
    echo.debug(f"{config_path=},\n{repository=}\n{branch=},\n{tag=},\n{directory=},\n{yes=}")
    if directory.is_dir():
        echo.error(f"Directory {directory} already exists.")
        raise typer.Exit(1)

    if not yes and not typer.confirm(f"Confirm installing DF Infra in {directory}"):
        raise typer.Exit(1)

    echo.info("Installing infra.")
    try:
        directory.mkdir(parents=True)
    except Exception as exc_info:
        echo.error("Unable to create infra directory.")
        reraise_if_debug(exc_info)

    git = Git(repository=repository)
    git.clone(branch=branch, tag=tag, directory=directory)

    # TODO Configure infra
