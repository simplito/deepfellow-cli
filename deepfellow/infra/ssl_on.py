# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Models ssl-on command."""

from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import typer

from deepfellow.common.defaults import DF_INFRA_NAME, DF_INFRA_PORT, DOCKER_COMPOSE_CONFIG_FILENAME
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
from deepfellow.common.system import run
from deepfellow.common.validation import validate_server
from deepfellow.infra.utils.admin import infra_admin_request
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


def _resolve_url(server: str | None, default: str) -> str:
    """Return the public URL of DeepFellow Infra, asking for it when `--url` wasn't given.

    Warns when the URL's host is the Infra service name, which resolves only inside the Docker network.
    """
    if server is None:
        server = cast(
            "str",
            echo.prompt_until_valid("Public https URL of DeepFellow Infra", validate_server, default=default),
        )

    if urlparse(server).hostname == DF_INFRA_NAME:
        echo.warning(
            f'"{DF_INFRA_NAME}" in {server} resolves only inside Docker. '
            "Pass --url with the public address of DeepFellow Infra."
        )

    return server


def _get_config_infra_url(admin_url: str, admin_api_key: str) -> str:
    """Read `infra_url` from the running Infra's config.json (GET /admin/config); "" if it isn't set."""
    config = infra_admin_request("GET", f"{admin_url}/admin/config", admin_url, admin_api_key)
    entries: list[dict[str, Any]] = config.get("entries", [])
    entry = next((entry for entry in entries if entry.get("field_name") == "infra_url"), {})
    return str(entry.get("value") or "")


@app.command()
def ssl_on(
    directory: Path = directory_option(exists=True),
    ssl_key_path: str = typer.Argument(None, help="Path to the SSL key path."),
    ssl_cert_path: str = typer.Argument(None, help="Path to the SSL certificate path."),
    port: int | None = typer.Option(None, help="Port to serve the SSL server from."),
    server: str | None = typer.Option(
        None, "--url", help="New SSL DeepFellow Infra address.", callback=validate_server
    ),
) -> None:
    """Switch on the SSL."""
    # Validate entry data
    check_infra_directory(directory)
    assert_docker()
    if (ssl_key_path and not ssl_cert_path) or (not ssl_key_path and ssl_cert_path):
        echo.error("SSL configuration requires both SSL_KEY_PATH and SSL_CERT_PATH. Provide both or omit both.")
        raise typer.Exit(1)

    # Load the compose file first: `docker compose ps` below needs it, so a missing one would read as "not running"
    docker_config = load_install_compose_file(directory, "infra", "Infra")

    # Check if Infra docker is running
    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    env_file = directory / ".env"
    # Infra keeps serving plain http on its current port until the restart below
    admin_url = local_url(
        env_get(env_file, "infra_port", default=str(DF_INFRA_PORT)) or DF_INFRA_PORT,
        env_get(env_file, "infra_bind_address", should_raise=False),
    )
    admin_api_key = env_get(env_file, "infra_admin_api_key", should_raise=False) or ""

    # Ask for the URL before changing anything: it also names the generated certificate
    config_url = _get_config_infra_url(admin_url, admin_api_key)
    env_url = env_get(env_file, "infra_url")
    server = _resolve_url(server, default=to_https(config_url or env_url or admin_url))

    # Add ssl-volume to docker compose if not there
    docker_infra = docker_config["services"]["infra"]
    ssl_dir = directory / "ssl"
    ssl_dir.mkdir(exist_ok=True)
    ssl_dir_str = ssl_dir.as_posix()
    if not any(ssl_dir_str in volume for volume in docker_infra["volumes"]):
        docker_infra["volumes"].append(f"{ssl_dir_str}:/ssl")

    save_compose_file(docker_config, compose_file=directory / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)

    # Create directory on the server
    run(["docker", "compose", "exec", "infra", "mkdir", "/ssl", "-p"], cwd=directory)

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
        echo.info("Creating cert files on the DeepFellow Infra.")
        run(
            [
                "docker",
                "compose",
                "exec",
                "infra",
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
                *self_signed_cert_name_args(server, DF_INFRA_NAME),
            ],
            cwd=directory,
            quiet=True,
        )
        echo.debug("Copying cert files from the DeepFellow Infra.")
        copy_ssl_files_from_service("infra", ssl_dir, cwd=directory)

    # Update .env with the port
    port_config = env_get(env_file, "infra_port")

    if port is not None and port != port_config:
        echo.info(f"Storing DF_INFRA_PORT as {port}")
        env_set(env_file, "infra_port", str(port), quiet=True)

    # Update the infra URL: the running Infra reads it from config.json, .env only seeds a fresh config.json
    if server != config_url:
        echo.info(f"Storing infra_url in config.json as {server}")
        infra_admin_request(
            "PUT", f"{admin_url}/admin/config", admin_url, admin_api_key, json_body={"infra_url": server}
        )

    if server != env_url:
        echo.info(f"Storing DF_INFRA_URL as {server}")
        env_set(env_file, "infra_url", server, quiet=True)

    enable_uvicorn_ssl(docker_infra)
    save_compose_file(docker_config, compose_file=directory / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)

    echo.info("Restarting docker.")
    # Restart docker with rebuild
    run(["docker", "compose", "down"], cwd=directory, quiet=True)
    run(["docker", "compose", "up", "--build", "-d", "--remove-orphans"], cwd=directory, quiet=True)

    echo.success(f"DeepFellow Infra is running with SSL on {server}.")
