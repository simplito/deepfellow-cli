# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Models ssl-on command."""

import shutil
from pathlib import Path

import typer

from deepfellow.common.docker import is_service_running, load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.system import run
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def ssl_on(
    directory: Path = directory_option(exists=True),
    ssl_key_path: str = typer.Argument(None, help="Path to the SSL key path."),
    ssl_cert_path: str = typer.Argument(None, help="Path to the SSL certificate path."),
    port: int = typer.Option(None, help="Port to serve the SSL server from."),
    server: str = typer.Option(None, help="New SSL DeepFellow Infra address.", callback=validate_server),
) -> None:
    """Switch on the SSL."""
    # Validate entry data
    if (ssl_key_path and not ssl_cert_path) or (not ssl_key_path and ssl_cert_path):
        echo.error("SSL configuration requires both SSL_KEY_PATH and SSL_CERT_PATH. Provide both or omit both.")
        raise typer.Exit(1)

    # Check if Infra docker is running
    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    # Add ssl-volume to docker compose if not there
    docker_config = load_compose_file(directory / "docker-compose.yml")
    env_file = directory / ".env"
    docker_infra = docker_config["services"]["infra"]
    ssl_dir = directory / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    ssl_dir_str = ssl_dir.as_posix()
    if not any(ssl_dir_str in volume for volume in docker_infra["volumes"]):
        docker_infra["volumes"].append(f"{ssl_dir_str}:/ssl")

    save_compose_file(docker_config, compose_file=directory / "docker-compose.yml", quiet=True)

    # Create directory on the server
    run("docker compose exec infra mkdir /ssl -p", cwd=directory)

    # If paths are provided - copy the files to the volume
    # Else run the openssl commands
    if ssl_key_path and ssl_cert_path:
        echo.debug(f"Copying cert files to the {ssl_dir}.")
        try:
            shutil.copy2(Path(ssl_key_path), ssl_dir / "key.pem")
            shutil.copy2(Path(ssl_cert_path), ssl_dir / "cert.pem")
        except FileNotFoundError as exc:
            echo.error(f"File not found {exc.filename}")
            raise typer.Exit(1) from exc
    else:
        echo.info("Creating cert files on the DeepFellow Infra.")
        run(
            "docker compose exec infra  "
            "openssl req -x509 -newkey rsa:4096 -nodes "
            "-out /ssl/cert.pem -keyout /ssl/key.pem -days 3650 -subj '/CN=localhost'",
            cwd=directory,
            quiet=True,
        )
        echo.debug("Copying cert files from the DeepFellow Infra.")
        run(f"docker compose cp infra:/ssl/. {ssl_dir}", cwd=directory, quiet=True)

    # Update .env with the port
    port_config = env_get(env_file, "infra_port")

    if port is not None and port != port_config:
        echo.info(f"Storing DF_INFRA_PORT as {port}")
        env_set(env_file, "infra_port", str(port), quiet=True)

    # Update the infra URL
    host = host_config = env_get(env_file, "infra_url")
    if server is None:
        if host and not host.startswith("https"):
            host = host.replace("http:", "https:")

        server = host

    if server is not None and server != host_config:
        echo.info(f"Storing DF_INFRA_URL as {server}")
        env_set(env_file, "infra_url", server, quiet=True)

    # Update docker compose with the command
    docker_infra["entrypoint"] = []
    docker_infra["command"] = (
        "./.venv/bin/uvicorn server.main:app"
        ' --host "0.0.0.0" --port 8086 --reload --log-level debug'
        " --ssl-keyfile /ssl/key.pem --ssl-certfile /ssl/cert.pem"
    )
    save_compose_file(docker_config, compose_file=directory / "docker-compose.yml", quiet=True)

    echo.info("Restarting docker.")
    # Restart docker with rebuild
    run("docker compose down", cwd=directory, quiet=True)
    run("docker compose up -d --build", cwd=directory, quiet=True)

    echo.success("DeepFellow Infra is running with SSL.")
