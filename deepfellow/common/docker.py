# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Docker helper methods."""

import ipaddress
import json
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer
import yaml

from deepfellow.common.config import env_to_dict, read_env_file
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, UVICORN_SSL_ENVS, ServiceConfig
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import DockerNetworkError, DockerSocketNotFoundError
from deepfellow.common.system import run

# Files `ssl-on` keeps in a service's `/ssl`, with their host permissions: the key is owner-only
SSL_FILE_MODES = {"key.pem": 0o600, "cert.pem": 0o644}


class DockerError(Exception):
    """Raised if any docker command fails."""


def _command_succeeds(cmd: list[str], catch_not_found: bool = True) -> bool:
    """Checks if a command runs successfully.

    Args:
        cmd: Command to run.
        catch_not_found: Whether a missing executable should also count as failure.
    """
    errors: tuple[type[Exception], ...] = (DockerError, FileNotFoundError) if catch_not_found else (DockerError,)
    try:
        run(cmd, capture_output=True, raises=DockerError)
    except errors:
        return False

    return True


def is_docker_installed() -> bool:
    """Checks if docker is installed."""
    return _command_succeeds(["docker", "--version"])


def is_docker_compose_installed() -> bool:
    """Checks if the docker compose plugin is installed."""
    return _command_succeeds(["docker", "compose", "version"])


def is_user_allowed_to_use_docker() -> bool:
    """Check is user is allowed to use docker."""
    return _command_succeeds(["docker", "ps"], catch_not_found=False)


def is_user_in_docker_group() -> bool:
    """Check is user is in docker group."""
    groups = run(["groups"], capture_output=True)
    return "docker" in groups if groups is not None else False


def is_docker_group_available() -> bool:
    """Check if group docker is present in the system."""
    group_file = Path("/etc/group")
    if not group_file.exists():
        return False

    return any(line.startswith("docker:") for line in group_file.read_text().splitlines())


def represent_none(self: yaml.representer.BaseRepresenter, _: None) -> yaml.ScalarNode:
    """Custom representer for None values.

    Required for volumes to generate:

    volumes:
      milvus:
      etcd:
    """
    return self.represent_scalar("tag:yaml.org,2002:null", "")


yaml.add_representer(type(None), represent_none)


def remove_old_docker_compose(compose_file: Path) -> None:
    """Remove old docker-compose.yml file.

    Args:
        compose_file: Project's compose file path
    """
    compose_file = compose_file.parent / "docker-compose.yml"
    compose_file.unlink(missing_ok=True)


def save_compose_file(
    compose_dict: dict[str, Any],
    compose_file: Path = Path(DOCKER_COMPOSE_CONFIG_FILENAME),
    quiet: bool = False,
    file_info: str = "Docker Compose configuration",
) -> None:
    """Saves Docker Compose configuration to YAML file."""
    compose_file.write_text(yaml.dump(compose_dict, default_flow_style=False, sort_keys=False, width=1000))
    msg = echo.debug if quiet else echo.info
    remove_old_docker_compose(compose_file)
    msg(f"Saved {file_info} to {compose_file.as_posix()}")


def load_compose_file(compose_file: Path = Path(DOCKER_COMPOSE_CONFIG_FILENAME)) -> dict[str, Any]:
    """Loads existing Docker Compose file and returns dictionary."""
    if not compose_file.exists():
        return {"services": {}}

    return yaml.safe_load(compose_file.read_text())


def load_install_compose_file(directory: Path, service: str, product: str) -> dict[str, Any]:
    """Load an install's Docker Compose file, exiting when it has no `service`.

    `load_compose_file` returns an empty file for a missing one, so without this check a command
    would only fail later, on the missing service, after it already asked questions or changed files.

    Args:
        directory: Directory of the install.
        service: Docker Compose service the install must have (e.g. `infra`, `server`).
        product: Name shown to the user (e.g. `Infra`, `Server`).

    Raises:
        typer.Exit: If the Docker Compose file is missing or has no `service`.
    """
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file)
    if service not in (compose.get("services") or {}):
        echo.error(f"No DeepFellow {product} installation in {directory}: {compose_file.name} is missing or incomplete")
        echo.info(f"Call `deepfellow {service} install`")
        raise typer.Exit(1)

    return compose


def _is_rootful_socket(socket_path: str) -> bool:
    """Checks whether the Docker socket belongs to a rootful Docker daemon.

    Args:
        socket_path: Path to the Docker socket.

    Returns:
        bool: True if the socket is owned by root, False otherwise or if it can't be inspected.
    """
    try:
        return Path(socket_path).stat().st_uid == 0
    except OSError:
        return False


def _find_socket() -> str:
    """Finds the active Docker socket path.

    Returns:
        str: the path to the socket

    Raises:
        DockerSocketNotFoundError: When unable to find the socket
    """
    if (docker_host := os.getenv("DOCKER_HOST")) and docker_host.startswith("unix://"):
        return docker_host.replace("unix://", "")

    # Try to find the active docker socket
    result = run(
        ["docker", "context", "inspect", "-f", "{{.Endpoints.docker.Host}}"],
        capture_output=True,
    )
    if result:
        host = result.strip()
        if host.startswith("unix://"):
            return host.replace("unix://", "")

    socket_file = "docker.sock"
    candidates: list[str] = []
    if xdg_runtime_dir := os.getenv("XDG_RUNTIME_DIR"):
        candidates.append(f"{xdg_runtime_dir}/{socket_file}")

    candidates.append(f"/run/user/{os.getuid()}/{socket_file}")
    candidates.append(f"/run/{socket_file}")

    for candidate in candidates:
        if Path(candidate).is_socket():
            return candidate

    raise DockerSocketNotFoundError(
        "Could not find the Docker socket. Checked DOCKER_HOST, "
        f"`docker context inspect` and {', '.join(candidates)}. "
        "Set DOCKER_HOST=unix:///path/to/docker.sock to point at it."
    )


def get_socket(allow_rootful: bool = False) -> str:
    """Get the Docker socket.

    Detect active docker socket with `DOCKER_HOST`, `docker context inspect`
    (https://docs.docker.com/reference/cli/docker/context/inspect/) or well-known paths.
    Warns when the socket belongs to rootful Docker, wherever the path came from.

    Args:
        allow_rootful: do not ask user if rootful Docker detected

    Returns:
        str: the path to the socket

    Raises:
        DockerSocketNotFoundError: When unable to find the socket
        typer.Exit: When rootful Docker detected and user declined to continue
    """
    socket_path = _find_socket()

    if _is_rootful_socket(socket_path):
        echo.warning(
            f"You're using rootful Docker ({socket_path}). "
            "The DeepFellow Infra container will get root-level access to the host. This is a security risk."
        )
        if not allow_rootful and not echo.confirm("Do you want to continue?", default=False, ignore_yes=True):
            echo.error("Aborted: rootful Docker not allowed. Re-run with --allow-rootful to continue anyway.")
            raise typer.Exit(1)

    return socket_path


def list_networks() -> list[str]:
    """Returns a list of all Docker network names.

    https://docs.docker.com/reference/cli/docker/network/ls#format

    Returns:
        list[str]: List of network names
        ['bridge', 'host', 'deepfellow-infra-net']

    Raises:
        DockerNetworkError: When unable to fetch network list
    """
    result = run(["docker", "network", "ls", "--format", "{{.Name}}"], capture_output=True)
    if result is None:
        raise DockerNetworkError("Failed to fetch Docker network list")

    networks = result.strip().split("\n")
    # Filter potential empty lines
    return [net for net in networks if net]


def create_network(network_name: str, driver: str = "bridge") -> None:
    """Creates a new Docker network.

    https://docs.docker.com/reference/cli/docker/network/create

    Args:
        network_name: Name of the network to create
        driver: Network driver (default: 'bridge')

    Returns:
        bool: True if network was created, False on error

    Raises:
        DockerNetworkError: When unable to create network
    """
    try:
        run(["docker", "network", "create", "--driver", driver, network_name], raises=DockerError, quiet=True)
        echo.debug(f"Created docker network {network_name}.")
    except DockerError as exc:
        raise DockerNetworkError(f"Failed to create network '{network_name}'") from exc


def ensure_network(network_name: str, driver: str = "bridge") -> None:
    """Ensures a Docker network exists. Creates it if it doesn't exist.

    Args:
        network_name: Name of the network
        driver: Network driver (default: 'bridge')

    Returns:
        bool: True if network exists or was created

    Raises:
        DockerNetworkError: When unable to list or create network
    """
    networks = list_networks()
    if network_name not in networks:
        create_network(network_name, driver)


def add_network_to_service(service: ServiceConfig | dict[str, Any], network_name: str) -> None:
    """Add a Docker network to a docker service's \"networks\" field.

    Args:
        service: Dictionary containing service configuration
        network_name: Name of the network

    Returns:
        None
    """
    service["networks"] = service.get("networks", [network_name])
    if network_name not in service["networks"]:
        service["networks"].append(network_name)


def is_all_interfaces(bind_address: str) -> bool:
    """Whether a port published on `bind_address` listens on every host interface.

    Args:
        bind_address: Host address the port is published on, as validated by `validate_bind_address`.
    """
    return not bind_address or ipaddress.ip_address(bind_address.strip("[]")).is_unspecified


def local_host(bind_address: str) -> str:
    """Host the CLI reaches a port published on `bind_address` at.

    Args:
        bind_address: Host address the port is published on, as validated by `validate_bind_address`.

    Returns:
        "localhost" when the port is published on all interfaces, otherwise the address itself.
    """
    return "localhost" if is_all_interfaces(bind_address) else bind_address


def local_url(port: str | int, bind_address: str | None) -> str:
    """URL the CLI reaches a port published on `bind_address` at.

    Args:
        port: Published host port.
        bind_address: Host address the port is published on; `None` (no value in `.env`, e.g. an
            install from before bind addresses existed) means all interfaces.
    """
    return f"http://{local_host(bind_address or '')}:{port}"


def to_https(url: str) -> str:
    """Return `url` with an `http://` scheme switched to `https://`; any other URL is returned unchanged."""
    return f"https://{url.removeprefix('http://')}" if url.startswith("http://") else url


def self_signed_cert_name_args(url: str, service: str) -> list[str]:
    """Return the `openssl req` arguments that name a self-signed certificate for a service.

    The certificate is issued for the host of `url` and is also valid for `localhost`, `127.0.0.1` and
    the service's name in the Docker network, so it verifies under any of the names the service is reached by.

    Args:
        url: Public URL of the service.
        service: Docker Compose service name (e.g. `infra`, `server`).
    """
    host = urlparse(url).hostname or "localhost"
    names = dict.fromkeys(["localhost", "127.0.0.1", service, host])
    alt_names = [f"IP:{name}" if _is_ip_address(name) else f"DNS:{name}" for name in names]
    return ["-subj", f"/CN={host}", "-addext", f"subjectAltName={','.join(alt_names)}"]


def _is_ip_address(value: str) -> bool:
    """Whether `value` is an IPv4 or IPv6 address rather than a host name."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False

    return True


def _is_unbound_port_mapping(port: object) -> bool:
    """Whether `port` is a plain `host:container` mapping with no host address.

    A mapping that names a host address, uses the long (mapping) syntax, or isn't a string at all
    (an unquoted mapping such as `2222:22`, which PyYAML reads as a base-60 int) doesn't count.
    """
    return isinstance(port, str) and port.count(":") == 1


def has_unbound_port_mappings(service: ServiceConfig | dict[str, Any]) -> bool:
    """Whether a Docker Compose service publishes a port with no host address (on all interfaces)."""
    return any(_is_unbound_port_mapping(port) for port in service.get("ports") or [])


def bind_port_mappings(service: ServiceConfig | dict[str, Any], bind_address: str) -> bool:
    """Prefix a Docker Compose service's port mappings that have no host address with `bind_address`.

    Args:
        service: Docker Compose service definition, updated in place.
        bind_address: Host address part to prepend, e.g. `INTERNAL_BIND_ADDRESS`.

    Returns:
        Whether any mapping was changed.
    """
    if not has_unbound_port_mappings(service):
        return False
    service["ports"] = [
        f"{bind_address}:{port}" if _is_unbound_port_mapping(port) else port for port in service["ports"]
    ]
    return True


def enable_uvicorn_ssl(service: dict[str, Any]) -> None:
    """Turn TLS on for a uvicorn-based Docker Compose service (Server, Infra) via `UVICORN_SSL_ENVS`.

    The image's CMD is kept, so the service starts with its usual port and flags.

    Args:
        service: Docker Compose service definition, updated in place.
    """
    environment = [env for env in service.get("environment", []) if env.split("=", 1)[0] not in UVICORN_SSL_ENVS]
    service["environment"] = [*environment, *(f"{key}={value}" for key, value in UVICORN_SSL_ENVS.items())]


def copy_ssl_files_from_service(service: str, ssl_dir: Path, cwd: Path) -> None:
    """Copy `key.pem` and `cert.pem` from a running service's `/ssl` into `ssl_dir` on the host.

    The files are read with `docker compose exec` because `docker compose cp` fails on some Docker
    versions for a container with a bind-mounted Docker socket (Infra). The key is written owner-only.

    Args:
        service: Docker Compose service name (e.g. `infra`, `server`).
        ssl_dir: Host directory to write the files to.
        cwd: Directory of the Docker Compose project.
    """
    for name, mode in SSL_FILE_MODES.items():
        content = run(["docker", "compose", "exec", "-T", service, "cat", f"/ssl/{name}"], cwd=cwd, capture_output=True)
        _write_ssl_file(ssl_dir / name, (content or "").encode(), mode)


def copy_ssl_files_from_paths(key_path: Path, cert_path: Path, ssl_dir: Path) -> None:
    """Copy a key and certificate given by the user into `ssl_dir` as `key.pem` and `cert.pem`.

    The key is written owner-only whatever the permissions of the source file.

    Args:
        key_path: Path to the user's key file.
        cert_path: Path to the user's certificate file.
        ssl_dir: Host directory to write the files to.

    Raises:
        FileNotFoundError: If either source file is missing; nothing is written then.
    """
    key, cert = key_path.read_bytes(), cert_path.read_bytes()
    _write_ssl_file(ssl_dir / "key.pem", key, SSL_FILE_MODES["key.pem"])
    _write_ssl_file(ssl_dir / "cert.pem", cert, SSL_FILE_MODES["cert.pem"])


def _write_ssl_file(path: Path, content: bytes, mode: int) -> None:
    """Write `content` to `path` with permissions `mode`."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    # os.open applies `mode` only to a new file, so an existing one gets it here, before the write
    os.fchmod(fd, mode)
    with os.fdopen(fd, "wb") as file:
        file.write(content)


def is_service_running(service: str, cwd: Path) -> bool:
    """Check if service is running."""
    result: str | None = None
    try:
        result = run(
            ["docker", "compose", "ps", service, "--status", "running"],
            cwd=cwd,
            raises=DockerError,
            capture_output=True,
        )
    except DockerError:
        return False

    # Running result:
    # NAME            IMAGE                                               ...
    # infra-infra-1   hub.simplito.com/deepfellow/deepfellow-infra:dev   ...

    # Not running result:
    # NAME            IMAGE                                               ...

    return result is not None and len(result.splitlines()) > 1


def get_running_service_image(service: str, cwd: Path) -> str | None:
    """Return the image reference the service's running container was created from.

    Returns `None` when the service is not running or `docker compose ps` fails - callers should
    treat that as "not confirmed up to date", never as a reason to skip work.
    """
    try:
        result = run(
            ["docker", "compose", "ps", service, "--status", "running", "--format", "{{.Image}}"],
            cwd=cwd,
            raises=DockerError,
            capture_output=True,
        )
    except DockerError:
        return None

    lines = (result or "").split()
    return lines[0] if lines else None


def is_service_running_or_raise(service: str, cwd: Path) -> bool:
    """Check if a Compose service is running, distinguishing confirmed absence from a `docker compose ps` failure.

    Unlike `is_service_running()`, raises `DockerError` instead of silently returning `False` when
    `docker compose ps` itself fails - for a caller about to make a destructive, one-way decision
    (e.g. skip a volume-copy safety check) based on "this service isn't running", treating an
    unrelated command failure the same as confirmed-not-running would make that decision silently,
    and wrongly, on bad information.

    Raises:
        DockerError: If `docker compose ps` fails for a reason other than a clean, parseable result.
    """
    result = run(
        ["docker", "compose", "ps", service, "--status", "running"],
        cwd=cwd,
        raises=DockerError,
        capture_output=True,
    )
    return result is not None and len(result.splitlines()) > 1


def volume_exists(name: str) -> bool:
    """Check if a Docker volume with the given name exists.

    False means "not detected", not "definitely absent" - a failed inspect (daemon down,
    permissions, wrong context) is reported the same way as a missing volume. Do not use this at a
    destructive decision point (e.g. deciding whether it's safe to wipe or overwrite something
    because a volume "doesn't exist") - use `volume_exists_or_raise()` there instead, so a
    transient inspect failure can't be silently mistaken for confirmed absence.

    https://docs.docker.com/reference/cli/docker/volume/inspect/
    """
    try:
        run(["docker", "volume", "inspect", name], capture_output=True, raises=DockerError)
    except DockerError as e:
        echo.debug(e)
        return False

    return True


def volume_exists_or_raise(name: str) -> bool:
    """Check if a Docker volume exists, distinguishing confirmed absence from an inspect failure.

    Unlike `volume_exists()`, only returns `False` when Docker itself confirms the volume is
    absent ("No such volume" in `docker volume inspect`'s stderr). Any other failure (daemon down,
    permissions, wrong Docker context) raises `DockerError` instead of silently reporting "not
    found" - for a caller about to make a destructive, one-way decision (skip a migration, wipe a
    volume) based on "this volume doesn't exist", treating an unrelated inspect failure the same
    as confirmed absence would make that decision silently, and wrongly, on bad information.

    https://docs.docker.com/reference/cli/docker/volume/inspect/

    Raises:
        DockerError: If the inspect failed for a reason other than the volume not existing.
    """
    try:
        run(["docker", "volume", "inspect", name], capture_output=True, raises=DockerError)
    except DockerError as e:
        if "no such volume" in str(e).lower():
            return False
        raise

    return True


def remove_volume(name: str) -> None:
    """Remove a Docker volume by name.

    https://docs.docker.com/reference/cli/docker/volume/rm/

    Raises:
        DockerError: If the removal fails.
    """
    try:
        run(["docker", "volume", "rm", name], capture_output=True, raises=DockerError)
    except DockerError as e:
        echo.debug(e)
        raise


def resolve_compose_volume_name(directory: Path, volume_key: str) -> str | None:
    """Resolve the real, project-scoped Docker volume name Compose would assign to a volume key.

    Docker Compose prefixes an unqualified volume name with its project name (by default the
    sanitized basename of ``directory``, unless overridden), so the volume's real name isn't
    knowable just from the key used in a compose file. This works even before a compose file has
    been written to ``directory``, by piping a minimal synthetic one into ``docker compose
    config`` via stdin and letting Compose resolve the project name from ``directory`` itself. A
    volume declared but not referenced by any service is dropped entirely from the resolved
    config (no ``volumes`` key at all), so a dummy service has to mount it for Compose to resolve
    and report its name; the service is never started, only used to make ``config`` include it.
    """
    synthetic_compose = yaml.dump(
        {
            "services": {"_probe": {"image": "busybox", "volumes": [f"{volume_key}:/data"]}},
            "volumes": {volume_key: {}},
        }
    )
    try:
        result = run(
            ["docker", "compose", "-f", "-", "config", "--format", "json"],
            cwd=directory,
            input=synthetic_compose,
            capture_output=True,
            raises=DockerError,
        )
    except DockerError as e:
        echo.debug(e)
        return None

    if not result:
        return None
    try:
        volume = (json.loads(result).get("volumes") or {}).get(volume_key) or {}
    except (AttributeError, JSONDecodeError) as e:
        echo.debug(e)
        return None
    return volume.get("name") if volume else None


def get_docker_network(directory: Path) -> str:
    """Get docker network setting."""
    env_file = directory / ".env"
    env_vars = read_env_file(env_file)
    env_content = env_to_dict(env_vars)
    return str(env_content.get("df_infra_docker_subnet", ""))


def parse_docker_compose_ps(data: str) -> dict[str, str]:
    """Parse the output of docker compose ps command.

    Args:
        data: The output string from docker compose ps

    Returns:
        Dictionary with container information keyed by column names
    """
    lines = data.splitlines()

    if len(lines) < 2:
        return {}

    header = lines[0]
    info = lines[1]

    # Find the start positions of each column header
    indexes = {}
    last_end = 0
    headers = header.split()

    for i, header_name in enumerate(headers):
        start = header.find(header_name, last_end)
        if i < len(headers) - 1:
            next_header = headers[i + 1]
            end = header.find(next_header, start)
        else:
            end = len(info)

        indexes[header_name] = (start, end)
        last_end = start + 1

    # Extract data for each column
    result = {}
    for header_name, (start, end) in indexes.items():
        value = info[start:end].strip()
        result[header_name] = value

    return result


def parse_docker_compose_usage(data: str) -> dict[str, str]:
    """Parse the output of docker stats command.

    Args:
        data: The output string from docker stats command

    Returns:
        Dictionary with container usage information
    """
    lines = data.splitlines()

    if len(lines) < 2:
        return {}

    header_line = lines[0]

    # Define the expected column headers in order (as they appear in docker stats)
    column_headers = ["CONTAINER ID", "NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %", "NET I/O", "BLOCK I/O", "PIDS"]

    # Find the start position of each column header
    indexes = {}
    for i, header_name in enumerate(column_headers):
        start = header_line.find(header_name)
        if start == -1:
            continue

        # Determine end position (start of next column or end of line)
        if i < len(column_headers) - 1:
            # Find where the next column starts
            next_start = len(header_line)
            for next_header in column_headers[i + 1 :]:
                next_pos = header_line.find(next_header)
                if next_pos != -1:
                    next_start = next_pos
                    break
            end = next_start
        else:
            end = len(header_line)

        indexes[header_name] = (start, end)

    # Process the first data line (skip header)
    data_line = lines[1]

    container_info = {}
    for header_name, (start, end) in indexes.items():
        # Extract substring respecting column bounds
        value = data_line[start:end].strip() if end <= len(data_line) else data_line[start:].strip()

        # Split MEM USAGE / LIMIT into two separate fields
        if header_name == "MEM USAGE / LIMIT":
            parts = value.split(" / ")
            if len(parts) == 2:
                container_info["MEM USAGE"] = parts[0].strip()
                container_info["MEM LIMIT"] = parts[1].strip()
        else:
            container_info[header_name] = value

    return container_info


def docker_ps(directory: Path, context: str) -> dict[str, str] | None:
    """Run docker compose ps command and display results."""
    # Execute docker compose ps command in the specified directory
    try:
        result = run(["docker", "compose", "ps", context], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to get docker status from {context}")
        return None

    # Check if the command returned any containers (header line + at least one data line)
    if not result or len(result.splitlines()) <= 1:
        echo.info(f"No {context} container is currently running.")
        return None

    # Parse the docker ps output into a structured dictionary
    parsed = parse_docker_compose_ps(result)

    # Validate parsing was successful
    if not parsed:
        echo.error("Error parsing docker ps")
        raise typer.Exit(1)

    return parsed


def get_container_id(directory: Path, context: str) -> str:
    """Run docker ps context -q."""
    try:
        result = run(["docker", "compose", "ps", context, "-q"], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to check container ID for {context}")
        raise typer.Exit(1) from e

    return str(result)


def docker_stats(directory: Path, context: str) -> dict[str, str] | None:
    """Run docker stats command and display results."""
    container_id = get_container_id(directory, context)
    try:
        result = run(["docker", "stats", container_id, "--no-stream"], cwd=directory, capture_output=True)
    except Exception as e:
        echo.debug(e)
        echo.error(f"Failed to get docker stats for {context}")
        return None

    if not result or len(result.splitlines()) <= 1:
        echo.info(f"No {context} container is currently running.")
        return None

    parsed = parse_docker_compose_usage(result)

    if not parsed:
        echo.error("Error parsing docker response")
        raise typer.Exit(1)

    return parsed


def print_docker_status(directory: Path, context: str) -> None:
    """Collect stats about docker and print them out."""
    ps_response = docker_ps(directory, context) or {}
    stat_response = docker_stats(directory, context) or {}
    response = ps_response | stat_response
    if not response:
        echo.error("Failed to get data from docker.")
        return

    # Display container information in a formatted output
    echo.info(
        f"image: {response.get('IMAGE', 'N/A')}"
        f"\ncreated: {response.get('CREATED', 'N/A')}"
        f"\nstatus: {response.get('STATUS', 'N/A')}"
        f"\nports: {response.get('PORTS', 'N/A')}"
        f"\nCPU: {response.get('CPU %', 'N/A')}"
        f"\nUsed memory: {response.get('MEM USAGE', 'N/A')}"
        f"\nMemory limit: {response.get('MEM LIMIT', 'N/A')}"
        f"\nNET I/O: {response.get('NET I/O', 'N/A')}"
        f"\nDisk I/O: {response.get('BLOCK I/O', 'N/A')}"
    )
