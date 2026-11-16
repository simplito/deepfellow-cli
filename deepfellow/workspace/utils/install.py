# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Workspace install logic."""

import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import typer
import yaml

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_WORKSPACE_IMAGE,
    DF_WORKSPACE_MONGO_DB,
    DF_WORKSPACE_PORT,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    MONGO_REPLICA_SET,
    WORKSPACE_APP_SERVICE,
    WORKSPACE_MONGO_SERVICE,
    WORKSPACE_MONGO_VOLUME,
    WORKSPACE_REDIS_IMAGE,
    WORKSPACE_REDIS_SERVICE,
    mongo_replica_set_service,
)
from deepfellow.common.docker import ensure_network, load_compose_file, save_compose_file
from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.exceptions import DockerNetworkError, InstallError
from deepfellow.common.generate import generate_password
from deepfellow.common.install import ensure_directory
from deepfellow.common.system import run
from deepfellow.common.validation import validate_bind_address
from deepfellow.workspace.utils.configure import ADMIN_KEYS, SMTP_REQUIRED_KEYS, SMTP_TRIGGER_KEYS
from deepfellow.workspace.utils.public_url import DEFAULT_PUBLIC_URL_PATTERN

MONGO_USER = "workspace"
MONGO_PASSWORD_KEY = "DF_WORKSPACE_MONGO_PASSWORD"
MONGO_KEY_KEY = "DF_WORKSPACE_MONGO_KEY"
MONGO_PASSWORD_LENGTH = 32
MONGO_KEY_LENGTH = 64
APP_SECRET_LENGTH = 48
MCP_AUTH_TOKEN_LENGTH = 48

# Values the app cannot start without that the user (not the CLI) supplies.
REQUIRED_VALUES = {
    "DF_SERVER_URL": "DeepFellow Server URL",
    "DF_SERVER_API_KEY": "DeepFellow Server project API key",
    "DF_SERVER_ORGANIZATION_ID": "DeepFellow Server organization id",
    "DF_SERVER_PROJECT_ID": "DeepFellow Server project id",
    "SMALL_MODEL": "Small model name served by DeepFellow Server",
}

# Stack settings kept in .env, so a reinstall without flags restores them (they are not app settings).
IMAGE_KEY = "DF_WORKSPACE_IMAGE"
PORT_KEY = "DF_WORKSPACE_PORT"
BIND_ADDRESS_KEY = "DF_WORKSPACE_BIND_ADDRESS"
DOCKER_NETWORK_KEY = "DF_WORKSPACE_DOCKER_NETWORK"
# Set to "true" while the app runs a locally built image, which must never be pulled.
LOCAL_IMAGE_KEY = "DF_WORKSPACE_LOCAL_IMAGE"
# What a failed start tells to do once the cause is fixed; a caller with its own way to retry passes another.
DEFAULT_RETRY_HINT = "run 'workspace install --force-install' again (secrets are kept)"
MONGO_MIGRATION_ATTEMPTS = 30
MONGO_MIGRATION_DELAY = 2.0
# Services of the stack's own Mongo and Redis, whose images `env set` keeps and `update` may change.
_IMAGE_PINNED_SERVICES = (WORKSPACE_MONGO_SERVICE, WORKSPACE_REDIS_SERVICE)


def resolve_stack_settings(
    existing: Mapping[str, str],
    image: str | None,
    port: int | None,
    bind_address: str | None,
    docker_network: str | None,
) -> tuple[str, int, str, str]:
    """Pick the image, port, bind address and Docker network: given value, else the previous install's, else default.

    Args:
        existing: The .env of a previous install (empty on a fresh install).
        image: Image given explicitly, or `None`.
        port: Port given explicitly, or `None`.
        bind_address: Bind address given explicitly (empty means all interfaces), or `None`.
        docker_network: Docker network given explicitly, or `None`.

    Returns:
        The image, port, bind address and Docker network to install with.

    Raises:
        InstallError: When a value kept in the existing .env is invalid.
    """
    stored_port = existing.get(PORT_KEY)
    if port is None and stored_port:
        try:
            port = int(stored_port)
        except ValueError:
            raise InstallError(f"Existing .env has an invalid {PORT_KEY} value ({stored_port!r}); fix it.") from None
        if not 1 <= port <= 65535:
            raise InstallError(f"Existing .env has an invalid {PORT_KEY} value ({stored_port!r}); fix it.")
    if bind_address is None:
        stored_bind = existing.get(BIND_ADDRESS_KEY, "")
        try:
            bind_address = validate_bind_address(stored_bind) or ""
        except typer.BadParameter:
            raise InstallError(
                f"Existing .env has an invalid {BIND_ADDRESS_KEY} value ({stored_bind!r}); fix it."
            ) from None
    return (
        image or existing.get(IMAGE_KEY) or DF_WORKSPACE_IMAGE,
        port or DF_WORKSPACE_PORT,
        bind_address,
        docker_network or existing.get(DOCKER_NETWORK_KEY) or DF_INFRA_DOCKER_NETWORK,
    )


def resolve_local_image(existing: Mapping[str, str], local_image: bool | None) -> bool:
    """Tell whether the app uses a locally built image: the given choice, else the previous install's.

    Args:
        existing: The .env of a previous install (empty on a fresh install).
        local_image: Choice given explicitly, or `None`.

    Returns:
        True when the image must not be pulled.
    """
    if local_image is not None:
        return local_image
    return existing.get(LOCAL_IMAGE_KEY, "").lower() == "true"


def apply_local_image(env: dict[str, str], local_image: bool) -> tuple[str, ...]:
    """Record the local-image choice in `env`.

    Args:
        env: The .env content, changed in place.
        local_image: Whether the app uses a locally built image.

    Returns:
        The keys to drop from a previous `.env` (the marker, when the image is not local).
    """
    if local_image:
        env[LOCAL_IMAGE_KEY] = "true"
        return ()
    env.pop(LOCAL_IMAGE_KEY, None)
    return (LOCAL_IMAGE_KEY,)


def read_existing_env(directory: Path) -> dict[str, str]:
    """Read the .env of a previous install.

    Args:
        directory: Install directory.

    Returns:
        The parsed .env, or an empty dict when there is none.
    """
    env_file = directory / ".env"
    if not env_file.is_file():
        return {}
    return {key: value.replace("$$", "$") for key, value in read_env_file(env_file).items()}


def read_installed_env(directory: Path) -> dict[str, str]:
    """Read the .env of an existing installation, exiting when there is none or it cannot be read.

    Args:
        directory: Install directory.

    Returns:
        The parsed .env.

    Raises:
        typer.Exit: When the .env is missing, empty or unreadable.
    """
    env_file = directory / ".env"
    try:
        env = read_existing_env(directory)
    except (OSError, UnicodeDecodeError) as exc:
        echo.error(f"Cannot read {env_file}: {exc}")
        raise typer.Exit(1) from exc
    if not env:
        echo.error(f"No settings in {env_file}. Run 'workspace install' first.")
        raise typer.Exit(1)
    return env


def build_env(
    existing: Mapping[str, str], passed: Mapping[str, str | None], port: int, reset: Iterable[str] = ()
) -> dict[str, str]:
    """Build the app's .env content.

    `APP_SECRET` is taken from `existing` and generated only when there is none, because changing it signs users
    out and makes stored MCP credentials unreadable. `MCP_AUTH_TOKEN` is likewise generated once, so the `/mcp`
    endpoint is never left open to the network; it is kept on reinstall unless a new one is passed. A value in
    `passed` replaces the existing one; a `None` or empty one keeps it.
    The password and keyfile of the stack's own Mongo are generated once too (only when no external `MONGO_DB_URL`
    is used), since the data volume is bound to them.
    `PUBLIC_URL` is `http://localhost:<port>` when neither source has it, and an existing value of
    that default form follows a changed `port`; any other existing value is kept.

    Args:
        existing: The .env of a previous install (empty on a fresh install).
        passed: Values given explicitly, keyed by .env name.
        port: Published app port, used for the default `PUBLIC_URL`.
        reset: Keys to drop from the result, even when a previous install had them (applied before `passed`).

    Returns:
        The .env content.

    Raises:
        InstallError: When a passed value contains a line break.
    """
    dropped = set(reset)
    env = {key: value for key, value in existing.items() if key not in dropped}
    env["APP_SECRET"] = existing.get("APP_SECRET") or generate_password(APP_SECRET_LENGTH)
    env["MCP_AUTH_TOKEN"] = existing.get("MCP_AUTH_TOKEN") or generate_password(MCP_AUTH_TOKEN_LENGTH)
    for key, value in passed.items():
        if not value:
            continue
        if "\n" in value or "\r" in value:
            raise InstallError(f"{key} must not contain a line break.")
        env[key] = value
    if not env.get("MONGO_DB_URL"):
        env[MONGO_PASSWORD_KEY] = existing.get(MONGO_PASSWORD_KEY) or generate_password(MONGO_PASSWORD_LENGTH)
        env[MONGO_KEY_KEY] = existing.get(MONGO_KEY_KEY) or generate_password(MONGO_KEY_LENGTH)
    current = env.get("PUBLIC_URL")
    if not passed.get("PUBLIC_URL") and (not current or DEFAULT_PUBLIC_URL_PATTERN.fullmatch(current)):
        env["PUBLIC_URL"] = f"http://localhost:{port}"
    return env


def missing_values(env: Mapping[str, str]) -> list[str]:
    """List the required keys that `env` lacks.

    Args:
        env: The .env content.

    Returns:
        Missing keys from `REQUIRED_VALUES`, in declaration order.
    """
    return [key for key in REQUIRED_VALUES if not env.get(key)]


def incomplete_groups(env: Mapping[str, str]) -> list[str]:
    """Describe the settings groups the app would refuse to start with, because they are only partly given.

    Args:
        env: The .env content.

    Returns:
        One message per incomplete group (admin account, e-mail); empty when all is fine.
    """
    problems = []
    for keys, required in ((ADMIN_KEYS, ADMIN_KEYS), (SMTP_TRIGGER_KEYS, SMTP_REQUIRED_KEYS)):
        if any(env.get(key) for key in keys) and (missing := [key for key in required if not env.get(key)]):
            problems.append(f"{', '.join(required)} must be given together (missing: {', '.join(missing)})")
    return problems


def build_compose(
    image: str,
    port: int,
    bind_address: str,
    docker_network: str,
    local_mongo: bool = True,
    local_redis: bool = True,
    local_image: bool = False,
) -> dict[str, Any]:
    """Build the Workspace stack: the app, its own password-protected single-node replica-set Mongo, and Redis.

    Mongo and Redis are only on the stack's private default network and publish no port. Only the app joins
    `docker_network`. The app's Mongo and Redis URLs are set in its `environment`, which takes precedence over
    `.env`, so the stack uses its own Mongo and Redis. An external one has no service here, and the app takes
    its URL from `.env`.

    Args:
        image: App image.
        port: Host port the app is published on.
        bind_address: Host address to publish on; empty means all interfaces.
        docker_network: Existing external network shared with DeepFellow Server.
        local_mongo: Run Mongo in the stack; otherwise `MONGO_DB_URL` in `.env` is used.
        local_redis: Run Redis in the stack; otherwise `REDIS_URL` in `.env` is used.
        local_image: The app image is built locally, so it is never pulled.

    Returns:
        The compose dict.
    """
    environment = ["HOST=0.0.0.0"]
    depends_on = {}
    services: dict[str, Any] = {}
    volumes: dict[str, None] = {}
    if local_mongo:
        environment += [
            f"MONGO_DB_URL=mongodb://{MONGO_USER}:${{{MONGO_PASSWORD_KEY}}}@{WORKSPACE_MONGO_SERVICE}:27017/"
            f"?replicaSet={MONGO_REPLICA_SET}&authSource=admin",
            f"MONGO_DB_NAME={DF_WORKSPACE_MONGO_DB}",
        ]
        depends_on[WORKSPACE_MONGO_SERVICE] = {"condition": "service_healthy"}
        services |= mongo_replica_set_service(
            WORKSPACE_MONGO_SERVICE, WORKSPACE_MONGO_VOLUME, MONGO_USER, MONGO_PASSWORD_KEY, MONGO_KEY_KEY
        )
        volumes[WORKSPACE_MONGO_VOLUME] = None
    if local_redis:
        environment.append(f"REDIS_URL=redis://{WORKSPACE_REDIS_SERVICE}:6379")
        depends_on[WORKSPACE_REDIS_SERVICE] = {"condition": "service_healthy"}
        services[WORKSPACE_REDIS_SERVICE] = {
            "container_name": WORKSPACE_REDIS_SERVICE,
            "image": WORKSPACE_REDIS_IMAGE,
            "restart": "always",
            "healthcheck": {
                "test": ["CMD", "redis-cli", "ping"],
                "interval": "5s",
                "timeout": "5s",
                "retries": 10,
                "start_period": "5s",
            },
        }
    app: dict[str, Any] = {
        "container_name": WORKSPACE_APP_SERVICE,
        "image": image,
        "restart": "always",
        "env_file": ["./.env"],
        "environment": environment,
        "ports": [f"{bind_address}:{port}:3000"],
        "networks": ["default", docker_network],
        # The image has no HEALTHCHECK and no curl/wget, but has bash. The port opens only after bootstrap
        # (DF Server health check, migrations, admin), so `up --wait` fails instead of reporting a crash loop.
        "healthcheck": {
            "test": ["CMD", "bash", "-c", "exec 3<>/dev/tcp/127.0.0.1/3000"],
            "interval": "5s",
            "timeout": "5s",
            "retries": 12,
            "start_period": "60s",
        },
    }
    if local_image:
        app["pull_policy"] = "never"
    if depends_on:
        app["depends_on"] = depends_on
    compose: dict[str, Any] = {"services": {WORKSPACE_APP_SERVICE: app, **services}}
    if volumes:
        compose["volumes"] = volumes
    compose["networks"] = {docker_network: {"external": True}}
    return compose


def has_unprotected_mongo(directory: Path, existing: Mapping[str, str]) -> bool:
    """Tell whether `directory` holds a Mongo data volume made before the stack's Mongo was password-protected.

    Such a volume has no root user, and the image creates one only on an empty data directory, so the user has to
    be added by hand (see `protect_existing_mongo`).

    Args:
        directory: Install directory.
        existing: The .env of the previous install.

    Returns:
        True when the previous compose.yaml has the Mongo volume but the previous .env no Mongo password.
    """
    if existing.get(MONGO_PASSWORD_KEY):
        return False
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    if not compose_file.is_file():
        return False
    return WORKSPACE_MONGO_VOLUME in (load_compose_file(compose_file).get("volumes") or {})


def protect_existing_mongo(directory: Path, password: str) -> None:
    """Start the stack's Mongo with authentication on an old data volume and create its root user.

    With authentication on and no user yet, mongod accepts a connection from its own host to create the first one
    (the "localhost exception"), so the user is created through `mongosh` inside the container. The password is
    passed through the environment, not the command line.

    Args:
        directory: Install directory, with the new compose.yaml already written.
        password: Password of the root user, as written to .env.

    Raises:
        InstallError: When Mongo does not start or the user cannot be created.
    """
    echo.info("Adding the root user to the existing Mongo data (it was created without a password).")
    run(["docker", "compose", "up", "-d", "--no-deps", WORKSPACE_MONGO_SERVICE], cwd=directory, raises=InstallError)
    script = (
        f'db.getSiblingDB("admin").createUser({{user: "{MONGO_USER}", pwd: process.env.MONGO_PW, roles: ["root"]}})'
    )
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        "MONGO_PW",
        WORKSPACE_MONGO_SERVICE,
        "mongosh",
        "--quiet",
        "--eval",
        script,
    ]
    attempt = 0
    while True:
        attempt += 1
        try:
            run(command, cwd=directory, raises=InstallError, quiet=True, extra_env={"MONGO_PW": password})
        except InstallError as exc:
            if attempt >= MONGO_MIGRATION_ATTEMPTS:
                raise InstallError(
                    "Could not add the root user to the existing Mongo data. Back up the Docker volume of "
                    f"'{WORKSPACE_MONGO_VOLUME}' and see the Mongo logs ('docker logs {WORKSPACE_MONGO_SERVICE}')."
                ) from exc
            time.sleep(MONGO_MIGRATION_DELAY)
        else:
            return


def current_service_images(directory: Path) -> dict[str, str]:
    """Read the images of the stack's own Mongo and Redis from the existing compose.yaml.

    Args:
        directory: Install directory.

    Returns:
        Image per service name, only for the services present (none for an external Mongo or Redis).

    Raises:
        InstallError: When compose.yaml cannot be read.
    """
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    if not compose_file.is_file():
        return {}
    try:
        compose = load_compose_file(compose_file)
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        raise InstallError(f"Cannot read {compose_file}: {exc}") from exc
    services = compose.get("services") if isinstance(compose, dict) else None
    if not isinstance(services, dict):
        return {}
    images = {}
    for name in _IMAGE_PINNED_SERVICES:
        service = services.get(name)
        if isinstance(service, dict) and service.get("image"):
            images[name] = str(service["image"])
    return images


def apply_service_images(compose: dict[str, Any], images: Mapping[str, str]) -> dict[str, Any]:
    """Set the image of the services in `images` that `compose` has; others are left alone.

    Args:
        compose: The compose dict, changed in place.
        images: Image per service name.

    Returns:
        The same compose dict.
    """
    services = compose.get("services", {})
    for name, image in images.items():
        if name in services:
            services[name]["image"] = image
    return compose


def build_stack_compose(env: Mapping[str, str], images: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Build the compose dict from the settings kept in `.env`.

    Args:
        env: The .env content, with the stack settings (image, port, bind address, Docker network).
        images: Images of the stack's own Mongo and Redis to use instead of the ones pinned in the CLI.

    Returns:
        The compose dict.

    Raises:
        InstallError: When a stack setting in `env` is invalid.
    """
    image, port, bind_address, docker_network = resolve_stack_settings(env, None, None, None, None)
    compose = build_compose(
        image,
        port,
        bind_address,
        docker_network,
        local_mongo=not env.get("MONGO_DB_URL"),
        local_redis=not env.get("REDIS_URL"),
        local_image=resolve_local_image(env, None),
    )
    return apply_service_images(compose, images or {})


def write_stack(
    directory: Path, env: Mapping[str, str], reset: Iterable[str] = (), images: Mapping[str, str] | None = None
) -> None:
    """Write `.env` and the compose.yaml built from it.

    Args:
        directory: Install directory.
        env: The .env content.
        reset: Keys to drop from an existing `.env`.
        images: Images of the stack's own Mongo and Redis to use instead of the ones pinned in the CLI.

    Raises:
        InstallError: When a stack setting in `env` is invalid or a file cannot be written.
    """
    compose = build_stack_compose(env, images)
    # Compose interpolates `$` in `env_file` values, so a literal `$` has to be written as `$$`.
    compose_env = {key: value.replace("$", "$$") for key, value in env.items()}
    try:
        save_env_file(directory / ".env", compose_env, docker_note=False, quiet=True, remove=reset, always_quote=True)
        save_compose_file(compose, directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    except OSError as exc:
        raise InstallError(f"Could not write the configuration in {directory}: {exc}") from exc


def validate_env(env: Mapping[str, str]) -> list[str]:
    """Check the settings the app needs, leaving the decision about incomplete groups to the caller.

    Args:
        env: The .env content.

    Returns:
        One message per settings group that is only partly given (see `incomplete_groups`).

    Raises:
        InstallError: When a required value is missing.
    """
    if missing := missing_values(env):
        raise InstallError(
            "Missing required values: " + ", ".join(f"{REQUIRED_VALUES[key]} ({key})" for key in missing)
        )
    return incomplete_groups(env)


def confirm_overwrite(directory: Path) -> bool:
    """Ask whether to reinstall over an existing directory, without suggesting to delete it.

    The directory holds `APP_SECRET`, so deleting it (as the generic overwrite hint suggests) would orphan the
    data kept in the Mongo volume.
    """
    echo.warning(f"Directory {directory} already exists (e.g. kept by 'workspace uninstall').")
    if not is_interactive():
        echo.info(
            "Non-interactive mode is ON. Pass --force-install to reinstall over it; "
            f"do not delete {directory}, its .env holds the secrets for the stored data."
        )
    return echo.confirm("Reinstall over the existing installation (secrets and data are kept)?", ignore_yes=True)


def install(
    directory: Path,
    image: str,
    port: int,
    bind_address: str,
    docker_network: str,
    existing: Mapping[str, str],
    passed: Mapping[str, str | None],
    force_install: bool,
    overwrite: bool | None = None,
    reset: Iterable[str] = (),
    local_image: bool = False,
    retry_hint: str = DEFAULT_RETRY_HINT,
) -> dict[str, str]:
    """Write the stack to `directory` and start it.

    Args:
        directory: Install directory.
        image: App image.
        port: Host port the app is published on.
        bind_address: Host address to publish on; empty means all interfaces.
        docker_network: Existing external network shared with DeepFellow Server.
        existing: The .env of a previous install in `directory` (empty on a fresh install).
        passed: Values given explicitly, keyed by .env name.
        force_install: Skip the overwrite question for an existing directory.
        overwrite: Answer to the overwrite question when already asked (see `confirm_overwrite`); `None` asks here.
        reset: .env keys of a previous install to forget (to go back to the local Mongo/Redis or turn SMTP off).
        local_image: The app image is built locally, so it is never pulled.
        retry_hint: What the error message tells to do after fixing the cause, for a caller with its own way to
            retry (`suite install --resume`).

    Returns:
        The .env content that was written.

    Raises:
        InstallError: When a required value is missing or invalid, or the stack fails to start.
        typer.Exit: When the user declines to overwrite an existing directory.
    """
    resets = tuple(reset)
    env = build_env(existing, passed, port, resets)
    resets += apply_local_image(env, local_image)
    if problems := validate_env(env):
        raise InstallError("; ".join(problems) + ".")
    env |= {
        IMAGE_KEY: image,
        PORT_KEY: str(port),
        BIND_ADDRESS_KEY: bind_address,
        DOCKER_NETWORK_KEY: docker_network,
    }
    local_mongo = not env.get("MONGO_DB_URL")
    if local_mongo and passed.get("MONGO_DB_NAME"):
        raise InstallError("MONGO_DB_NAME applies to an external MongoDB only; give MONGO_DB_URL as well.")

    if overwrite is None and directory.is_dir() and not force_install:
        overwrite = confirm_overwrite(directory)
    ensure_directory(directory, force_install=force_install, overwrite=overwrite)
    migrate_mongo = local_mongo and has_unprotected_mongo(directory, existing)
    env_file = directory / ".env"
    previous_env = env_file.read_text() if env_file.is_file() else None
    write_stack(directory, env, resets)

    try:
        try:
            ensure_network(docker_network)
            if migrate_mongo:
                protect_existing_mongo(directory, env[MONGO_PASSWORD_KEY])
        except BaseException:
            # Keep the old .env (no Mongo password) whenever the root user was not created, also on a failed network
            # or an interrupt, so that a rerun still sees an unprotected Mongo to migrate.
            if migrate_mongo and previous_env is not None:
                env_file.write_text(previous_env)
            raise
        echo.info("Starting DeepFellow Workspace.")
        run(["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=directory, raises=InstallError)
    except (DockerNetworkError, InstallError) as exc:
        detail = str(exc) if str(exc) not in ("", "None") else "see the Docker output above"
        raise InstallError(
            f"Starting DeepFellow Workspace failed: {detail}. The configuration stays in {directory}; "
            f"fix the cause and {retry_hint}, or run 'workspace uninstall' to remove the containers."
        ) from exc
    return env
