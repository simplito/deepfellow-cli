# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Moving a local MongoDB from before the least-privilege account to one on `server update`.

Installs from before cli#283 started the local `mongo` service with `DF_MONGO_USER` as its root
account, so the server has been connecting with root privileges. Newer installs keep the root
account in `DF_MONGO_INITDB_ROOT_*` and give the server an account with `readWrite` on its
database only (created by `init-mongo.sh`, which MongoDB runs only on an empty data volume - never
on these installs).
"""

import json
from pathlib import Path

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, DOCKER_COMPOSE_MONGO_DB, MONGO_DB_INIT_SH
from deepfellow.common.docker import (
    ensure_network,
    get_docker_network,
    is_service_running,
    load_compose_file,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.common.generate import generate_password
from deepfellow.common.system import run

LEGACY_MONGO_ROOT_ENVS = (
    "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_USER}",
    "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_PASSWORD}",
)
MONGO_ENVS = tuple(
    env
    for env in DOCKER_COMPOSE_MONGO_DB["mongo"]["environment"]
    if env.startswith(("MONGO_INITDB_ROOT_", "DF_MONGO_"))
)
INIT_MONGO_SH_VOLUME = "./init-mongo.sh:/docker-entrypoint-initdb.d/init-mongo.sh:ro"


class MongoMigrationError(Exception):
    """Raised when the least-privilege MongoDB account can't be created or verified."""


def is_legacy_mongo_install(directory: Path) -> bool:
    """Return whether the install's local MongoDB still uses the server's account as its root account.

    Decided from `compose.yaml`, which the migration rewrites last, so an interrupted migration is
    still detected (and finished) by the next `server update`. An install with an external MongoDB
    has no `mongo` service and is never migrated.
    """
    compose = load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    mongo = compose.get("services", {}).get("mongo")
    if mongo is None:
        return False
    environment = mongo.get("environment", [])
    return all(env in environment for env in LEGACY_MONGO_ROOT_ENVS)


def _mongosh(directory: Path, statements: list[str]) -> None:
    """Run mongosh statements in the `mongo` container, passed on stdin so no secret shows up in arguments.

    The statements are wrapped in a `try`/`catch` that prints the error and does `quit(1)` - mongosh exits
    with 0 after an uncaught error in a stdin script.
    """
    body = "\n".join(f"  {statement}" for statement in statements)
    script = f"try {{\n{body}\n}} catch (error) {{\n  print(error.message);\n  quit(1);\n}}\n"
    run(
        ["docker", "compose", "exec", "-T", "mongo", "mongosh", "--quiet"],
        cwd=directory,
        raises=MongoMigrationError,
        capture_output=True,
        input=script,
    )


def _create_app_user(directory: Path, user: str, password: str, database: str) -> None:
    """Create the server's account with `readWrite` on its database only, as `init-mongo.sh` does.

    Authenticates as root with the credentials the running container was started with, so they
    are read inside the container rather than passed to it.
    """
    new_user = {"user": user, "pwd": password, "roles": [{"role": "readWrite", "db": database}]}
    _mongosh(
        directory,
        [
            'db.getSiblingDB("admin").auth('
            "process.env.MONGO_INITDB_ROOT_USERNAME, process.env.MONGO_INITDB_ROOT_PASSWORD);",
            f'db.getSiblingDB("admin").createUser({json.dumps(new_user)});',
        ],
    )


def _verify_app_user(directory: Path, user: str, password: str, database: str) -> None:
    """Check the server's new account can log in and read its database."""
    _mongosh(
        directory,
        [
            f'db.getSiblingDB("admin").auth({json.dumps(user)}, {json.dumps(password)});',
            f"db.getSiblingDB({json.dumps(database)}).getCollectionNames();",
        ],
    )


def _switch_to_app_user(directory: Path, env_file: Path, envs: dict[str, str]) -> None:
    """Create and verify the server's new account, then store it in `.env`, keeping the old one as root.

    The root account stays as it was, so a server still running with it keeps working until it is
    restarted with the new one.
    """
    user = generate_password(8)
    password = generate_password(12)
    database = envs["DF_MONGO_DB"]

    started_mongo = not is_service_running("mongo", directory)
    if started_mongo:
        ensure_network(get_docker_network(directory))
        run(
            ["docker", "compose", "up", "-d", "--wait", "mongo"],
            cwd=directory,
            raises=MongoMigrationError,
            capture_output=True,
        )
    try:
        _create_app_user(directory, user, password, database)
        _verify_app_user(directory, user, password, database)
    finally:
        # Left as it was found: the server's own restart or start brings it up again. Failing to
        # stop it doesn't undo the account switch, so it's only reported.
        if started_mongo:
            try:
                run(["docker", "compose", "stop", "mongo"], cwd=directory, raises=MongoMigrationError, quiet=True)
            except MongoMigrationError:
                echo.warning(
                    "MongoDB was started for the account switch but couldn't be stopped - stop it with "
                    f"`docker compose stop mongo` in {directory.as_posix()}."
                )

    save_env_file(
        env_file,
        {
            "DF_MONGO_INITDB_ROOT_USERNAME": envs["DF_MONGO_USER"],
            "DF_MONGO_INITDB_ROOT_PASSWORD": envs["DF_MONGO_PASSWORD"],
            "DF_MONGO_USER": user,
            "DF_MONGO_PASSWORD": password,
        },
        quiet=True,
    )


def _update_compose(directory: Path) -> None:
    """Set up the `mongo` service as new installs do: root from `DF_MONGO_INITDB_ROOT_*`, `init-mongo.sh` mounted."""
    init_mongo_path = directory / "init-mongo.sh"
    init_mongo_path.write_text(MONGO_DB_INIT_SH)
    init_mongo_path.chmod(0o755)

    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file)
    mongo = compose["services"]["mongo"]
    environment = [env for env in mongo.get("environment", []) if env not in LEGACY_MONGO_ROOT_ENVS]
    environment.extend(env for env in MONGO_ENVS if env not in environment)
    mongo["environment"] = environment
    volumes = mongo.setdefault("volumes", [])
    if INIT_MONGO_SH_VOLUME not in volumes:
        volumes.append(INIT_MONGO_SH_VOLUME)
    save_compose_file(compose, compose_file, quiet=True)


def migrate_mongo_to_app_user(directory: Path) -> bool:
    """Switch a legacy install's server from MongoDB's root account to a least-privilege one. No prompts.

    Never breaks the install: on any failure nothing is changed (or, past the `.env` write, only
    `compose.yaml` is left to finish), a warning is shown, and the next `server update` retries.

    Args:
        directory: The server install directory, already known to be legacy (`is_legacy_mongo_install`).

    Returns:
        Whether the server's MongoDB account changed, i.e. it needs a restart to use the new one.
    """
    env_file = directory / ".env"
    envs = read_env_file(env_file)
    # `.env` already has the root account kept apart: an earlier run got past the `.env` write
    # but not the `compose.yaml` one, so only that is left to do.
    already_switched = "DF_MONGO_INITDB_ROOT_USERNAME" in envs
    missing = [key for key in ("DF_MONGO_USER", "DF_MONGO_PASSWORD", "DF_MONGO_DB") if not envs.get(key)]
    if not already_switched and missing:
        echo.warning(
            f"MongoDB still uses its root account for DeepFellow Server, but {', '.join(missing)} "
            "is missing from .env - skipping the switch to a least-privilege account."
        )
        return False

    echo.info("Switching DeepFellow Server from MongoDB's root account to a least-privilege one...")
    try:
        if not already_switched:
            _switch_to_app_user(directory, env_file, envs)
        _update_compose(directory)
    except (MongoMigrationError, DockerNetworkError, OSError) as exc:
        echo.warning(
            "Couldn't switch DeepFellow Server to a least-privilege MongoDB account - the install keeps working "
            "as before, and the next `deepfellow server update` tries again."
        )
        echo.debug(f"MongoDB account switch failed: {getattr(exc.__cause__, 'stdout', None) or exc}")
        return False

    echo.success("DeepFellow Server now uses a MongoDB account limited to its own database.")
    return True
