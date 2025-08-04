"""Install server typer command."""

import shutil
from pathlib import Path
from uuid import uuid4

import typer
from rich.progress import Progress

from deepfellow.common.defaults import DF_SERVER_DIRECTORY, DF_SERVER_REPO
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.git import Git
from deepfellow.common.system import run

app = typer.Typer()


def clone_repo(repository: str, branch: str | None, tag: str | None, directory: Path) -> None:
    """Clone the repository to the directory."""
    try:
        directory.mkdir(parents=True)
    except Exception as exc_info:
        echo.error(f"Unable to create infra directory - {directory}.")
        reraise_if_debug(exc_info)

    with Progress(transient=True) as progress:
        progress.add_task("\tCloning repository...", start=False, total=None)
        git = Git(repository=repository)
        git.clone(branch=branch, tag=tag, directory=directory)


def configure_installation(directory: Path, env_file: Path) -> None:
    """Configure the installation."""
    shutil.copy(directory / "example.env", env_file)
    # TODO Ask a few questions anf fill in the secret details
    # Generate DF_ADMIN_KEY
    admin_key = uuid4()
    original_env_content = env_file.read_text().splitlines()
    new_env_content = []
    for line in original_env_content:
        if line.startswith("DF_ADMIN_KEY"):
            new_env_content.append(f"DF_ADMIN_KEY={admin_key}")
        else:
            new_env_content.append(line)

    echo.debug(str(new_env_content))
    env_file.write_text("\n".join(new_env_content))
    if echo.confirm(
        "Generated DF_ADMIN_KEY in the configuration file.\nDo you want me to display it now?", default=True
    ):
        echo.info(str(admin_key))
    else:
        echo.info("You can display it by running:\n`grep DF_ADMIN_KEY {env_file}`")


@app.command()
def install(
    ctx: typer.Context,
    repository: str = typer.Option(DF_SERVER_REPO, envvar="DF_SERVER_REPO", help="Git repository of server."),
    branch: str | None = typer.Option(None, help="Specify a branch to install from"),
    tag: str | None = typer.Option(None, help="Specify a tag to install from"),
    directory: Path = typer.Option(
        DF_SERVER_DIRECTORY, envvar="DF_SERVER_DIRECTORY", help="Target directory for the server installation."
    ),
) -> None:
    """Install server."""
    debug = ctx.obj.get("debug", False)
    yes = ctx.obj.get("yes", False)
    echo.debug(f"{repository=}\n{branch=},\n{tag=},\n{directory=},\n{yes=}")
    omit_pulling_repository = False
    if directory == DF_SERVER_DIRECTORY:
        directory = Path(echo.prompt("Provide directory for installation", default=str(directory)))

    if directory.is_dir():
        echo.warning(f"Directory {directory} already exists.")
        omit_pulling_repository = echo.confirm("Should I proceed installation with the existing code?")
        if not omit_pulling_repository:
            raise typer.Exit(1)

    if (
        not omit_pulling_repository  # We already asked the question about installation
        and not yes  # auto-confirm mode is on
        and not echo.confirm(f"Confirm installing DF Server in {directory}", default=True)
    ):
        raise typer.Exit(1)

    echo.info("Installing DF Server.")
    if not omit_pulling_repository:
        clone_repo(repository, branch, tag, directory)

    # Install dependencies
    echo.info("Installing dependencies...")
    command = "uv sync"
    if not debug:
        command += " --quiet"

    run(command, cwd=directory)

    # Configuration
    env_file = directory / ".env"
    if not omit_pulling_repository or echo.confirm(
        "Do you want to override the existing DF server configuration?", default=False
    ):
        configure_installation(directory, env_file)

    echo.success("DF Server installed.")

    echo.info(
        "Edit the configuration file to provide the appropriate values for your installation.\n"
        f"`vi {env_file}`\n"
        "Continue the installation by running: `deepfellow server install-continue`"
    )
    echo.debug("TODO Can we edit the Infra config?")
