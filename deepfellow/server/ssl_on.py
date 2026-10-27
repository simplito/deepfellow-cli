# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Models ssl-on command."""

from pathlib import Path
from typing import cast
from urllib.parse import urlparse

import typer

from deepfellow.common.defaults import DF_SERVER_PORT, DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.docker import (
    copy_ssl_files_from_paths,
    copy_ssl_files_from_service,
    enable_uvicorn_ssl,
    is_service_running,
    load_install_compose_file,
    local_url,
    save_compose_file,
    self_signed_cert_name_args,
    to_https,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.rest import get as http_get
from deepfellow.common.rest import make_request
from deepfellow.common.state import state
from deepfellow.common.system import run
from deepfellow.common.validation import validate_server
from deepfellow.server.utils.login import get_token
from deepfellow.server.utils.options import directory_option

app = typer.Typer()

# The server's Docker Compose service name, which is also its host name inside the Docker network
SERVER_SERVICE = "server"


def _resolve_url(server: str | None, default: str) -> str:
    """Return the public URL of DeepFellow Server, asking for it when `--url` wasn't given.

    Warns when the URL's host is the Server service name, which resolves only inside the Docker network.
    """
    if server is None:
        server = cast(
            "str",
            echo.prompt_until_valid("Public https URL of DeepFellow Server", validate_server, default=default),
        )

    if urlparse(server).hostname == SERVER_SERVICE:
        echo.warning(
            f'"{SERVER_SERVICE}" in {server} resolves only inside Docker. '
            "Pass --url with the public address of DeepFellow Server."
        )

    return server


@app.command()
def ssl_on(
    directory: Path = directory_option(exists=True),
    ssl_key_path: str | None = typer.Argument(None, help="Path to the SSL key path."),
    ssl_cert_path: str | None = typer.Argument(None, help="Path to the SSL certificate path."),
    port: int | None = typer.Option(None, help="Port to serve the SSL server from."),
    server: str | None = typer.Option(
        None, "--url", help="New SSL DeepFellow Server address.", callback=validate_server
    ),
) -> None:
    """Switch on the SSL."""
    # TODO Add check directory if done
    assert_docker()

    # Validate entry data
    if (ssl_key_path and not ssl_cert_path) or (not ssl_key_path and ssl_cert_path):
        echo.error("SSL configuration requires both SSL_KEY_PATH and SSL_CERT_PATH. Provide both or omit both.")
        raise typer.Exit(1)

    # Load the compose file first: `docker compose ps` below needs it, so a missing one would read as "not running"
    docker_config = load_install_compose_file(directory, "server", "Server")

    # Check if Server docker is running
    if not is_service_running("server", cwd=directory):
        echo.error("DeepFellow Server is not running")
        echo.info("Call `deepfellow server start`")
        raise typer.Exit(1)

    env_file = directory / ".env"
    # The server keeps serving plain http on its current port until the restart below
    admin_url = local_url(
        env_get(env_file, "server_port", default=str(DF_SERVER_PORT)) or DF_SERVER_PORT,
        env_get(env_file, "server_bind_address", should_raise=False),
    )

    # Ask for the URL before changing anything: it also names the generated certificate
    token = get_token(state.cli_secrets_file, admin_url)
    config_url = http_get(f"{admin_url}/admin/config", token, item_name="Server config").get("server_url")
    env_url = env_get(env_file, "server_url")
    server = _resolve_url(server, default=to_https(config_url or env_url or admin_url))

    # Add ssl-volume to docker compose if not there
    docker_server = docker_config["services"]["server"]
    ssl_dir = directory / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    ssl_dir_str = ssl_dir.as_posix()
    if not any(ssl_dir_str in volume for volume in docker_server["volumes"]):
        docker_server["volumes"].append(f"{ssl_dir_str}:/ssl")

    save_compose_file(docker_config, compose_file=directory / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)

    # Create directory on the server
    run(["docker", "compose", "exec", "server", "mkdir", "/ssl", "-p"], cwd=directory)

    # If paths are provided - copy the files to the volume
    # Else run the openssl commands
    if ssl_key_path and ssl_cert_path:
        echo.debug(f"Copying cert files to the {ssl_dir}.")
        try:
            copy_ssl_files_from_paths(Path(ssl_key_path), Path(ssl_cert_path), ssl_dir)
        except FileNotFoundError as exc:
            echo.error(f"File not found {exc.filename}")
            raise typer.Exit(1) from exc
    else:
        echo.info("Creating cert files on the DeepFellow Server.")
        run(
            [
                "docker",
                "compose",
                "exec",
                "server",
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-nodes",
                "-out",
                "/ssl/cert.pem",
                "-keyout",
                "/ssl/key.pem",
                "-days",
                "3650",
                *self_signed_cert_name_args(server, SERVER_SERVICE),
            ],
            cwd=directory,
            quiet=True,
        )
        echo.debug("Copying cert files from the DeepFellow server.")
        copy_ssl_files_from_service("server", ssl_dir, cwd=directory)

    # Update .env with the port
    port_config = env_get(env_file, "server_port")

    if port is not None and port != port_config:
        echo.info(f"Storing DF_server_PORT as {port}")
        env_set(env_file, "server_port", str(port), quiet=True)

    # Update the server URL: the running server reads it from config.json, not from .env
    if server != config_url:
        echo.info(f"Storing server_url in config.json as {server}")
        make_request(
            "PUT",
            f"{admin_url}/admin/config",
            token,
            data={"server_url": server},
            err_msg="Unable to update server config.",
        )

    if server != env_url:
        echo.info(f"Storing DF_SERVER_URL as {server}")
        env_set(env_file, "server_url", server, quiet=True)

    enable_uvicorn_ssl(docker_server)
    save_compose_file(docker_config, compose_file=directory / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)

    echo.info("Restarting docker.")
    # Restart docker with rebuild
    run(["docker", "compose", "down"], cwd=directory, quiet=True)
    run(["docker", "compose", "up", "--build", "-d", "--remove-orphans"], cwd=directory, quiet=True)

    echo.success(f"DeepFellow Server is running with SSL on {server}.")
