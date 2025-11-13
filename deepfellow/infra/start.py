"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import env_to_dict, read_env_file
from deepfellow.common.docker import ensure_network
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def start(
    directory: Path = directory_option(callback=validate_directory),
) -> None:
    """Start DeepFellow Infra."""
    echo.info("Starting DeepFellow Infra")

    env_file = directory / ".env"
    env_vars = read_env_file(env_file)
    env_content = env_to_dict(env_vars)
    docker_network = env_content.get("df_infra_docker_subnet", "")
    ensure_network(str(docker_network))
    run("docker compose up -d --wait", cwd=directory)
