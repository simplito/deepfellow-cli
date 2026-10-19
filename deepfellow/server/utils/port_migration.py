# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Binding the published ports of an install from before bind addresses to a host address on `server update`.

New installs publish the internal services' ports (the local MongoDB, and every port `--dev` adds)
on `DF_INTERNAL_BIND_ADDRESS` (127.0.0.1 by default) and the server's own port on
`DF_SERVER_BIND_ADDRESS`. Older installs have no host address in these mappings, so Docker
publishes them on all interfaces: the local MongoDB since CLI v0.31.0, and every internal service
in installs from before March 2026 or made with `--dev`.
"""

from pathlib import Path

from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, INTERNAL_BIND_ADDRESS, SERVER_BIND_ADDRESS
from deepfellow.common.docker import (
    bind_port_mappings,
    has_unbound_port_mappings,
    load_compose_file,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.state import state

# Every service a server install (of any CLI version) creates whose port is internal-only. A
# service the user added to compose.yaml themselves, e.g. a reverse proxy, is never touched.
INTERNAL_SERVICES = frozenset(
    {"mongo", "qdrant", "milvus", "etcd", "minio", "seaweedfs", "falkordb", "rabbitmq", "otel-collector"}
)


def migrate_port_bindings(directory: Path) -> bool:
    """Give an install's published ports the host address new installs have.

    `server`'s port gets the `DF_SERVER_BIND_ADDRESS` host part - with that variable unset it still
    listens on all interfaces, this only lets the variable take effect. The internal services' ports
    get the `DF_INTERNAL_BIND_ADDRESS` host part, which moves them to 127.0.0.1 - so this asks first,
    unless the variable is already set. Declining sets it empty instead: the ports stay on all
    interfaces and the question isn't asked again on the next update.

    Either change only takes effect once the services are recreated, e.g. by `server restart`.

    Args:
        directory: The server install directory.

    Returns:
        Whether the internal services' ports are being moved off all interfaces.
    """
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file)
    services = compose["services"]

    changed = "server" in services and bind_port_mappings(services["server"], SERVER_BIND_ADDRESS)

    internal = [
        service
        for name, service in services.items()
        if name in INTERNAL_SERVICES and has_unbound_port_mappings(service)
    ]
    restricted = False
    if internal:
        env_file = directory / ".env"
        if env_get(env_file, "DF_INTERNAL_BIND_ADDRESS", should_raise=False) is None:
            restricted = state.yes or echo.confirm(
                "MongoDB and other internal services are published on all network interfaces. "
                "Restrict them to 127.0.0.1?",
                default=True,
            )
            if not restricted:
                env_set(env_file, "DF_INTERNAL_BIND_ADDRESS", "", quiet=True, docker_note=False)
        for service in internal:
            bind_port_mappings(service, INTERNAL_BIND_ADDRESS)
        changed = True

    if changed:
        save_compose_file(compose, compose_file, quiet=True)
    if restricted:
        echo.info(
            "Internal service ports will be published on 127.0.0.1 only. To reach them from other hosts "
            'again: `deepfellow server env set INTERNAL_BIND_ADDRESS ""`.'
        )
    return restricted
