# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, INTERNAL_BIND_ADDRESS, SERVER_BIND_ADDRESS
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.server.utils.port_migration import migrate_port_bindings


def _old_install_services() -> dict:
    return {
        "server": {"image": "server", "ports": ["${DF_SERVER_PORT}:8000"]},
        "mongo": {"image": "mongo", "ports": ["${DF_MONGO_PORT}:27017"]},
        "qdrant": {"image": "qdrant", "ports": ["6333:6333", "6334:6334"]},
        "proxy": {"image": "caddy", "ports": ["443:443"]},
    }


@pytest.fixture
def old_install(tmp_path: Path) -> Path:
    save_compose_file({"services": _old_install_services()}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)
    save_env_file(tmp_path / ".env", {"DF_SERVER_PORT": "8000"}, quiet=True)
    return tmp_path


def _services(directory: Path) -> dict:
    return load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]


@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_restricts_internal_ports_when_confirmed(mock_echo: Mock, old_install: Path) -> None:
    mock_echo.confirm.return_value = True

    result = migrate_port_bindings(old_install)

    services = _services(old_install)
    assert result is True
    assert mock_echo.confirm.call_count == 1
    assert services["server"]["ports"] == [f"{SERVER_BIND_ADDRESS}:${{DF_SERVER_PORT}}:8000"]
    assert services["mongo"]["ports"] == [f"{INTERNAL_BIND_ADDRESS}:${{DF_MONGO_PORT}}:27017"]
    assert services["qdrant"]["ports"] == [f"{INTERNAL_BIND_ADDRESS}:6333:6333", f"{INTERNAL_BIND_ADDRESS}:6334:6334"]
    assert services["proxy"]["ports"] == ["443:443"]
    assert "DF_INTERNAL_BIND_ADDRESS" not in read_env_file(old_install / ".env")


@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_keeps_internal_ports_on_all_interfaces_when_declined(
    mock_echo: Mock, old_install: Path
) -> None:
    mock_echo.confirm.return_value = False

    result = migrate_port_bindings(old_install)

    assert result is False
    assert _services(old_install)["mongo"]["ports"] == [f"{INTERNAL_BIND_ADDRESS}:${{DF_MONGO_PORT}}:27017"]
    assert read_env_file(old_install / ".env")["DF_INTERNAL_BIND_ADDRESS"] == ""


@mock.patch("deepfellow.server.utils.port_migration.state")
@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_restricts_without_asking_with_yes(
    mock_echo: Mock, mock_state: Mock, old_install: Path
) -> None:
    mock_state.yes = True

    result = migrate_port_bindings(old_install)

    assert result is True
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_does_not_ask_when_internal_bind_address_already_set(
    mock_echo: Mock, old_install: Path
) -> None:
    save_env_file(old_install / ".env", {"DF_INTERNAL_BIND_ADDRESS": ""}, quiet=True)

    result = migrate_port_bindings(old_install)

    assert result is False
    assert mock_echo.confirm.call_count == 0
    assert _services(old_install)["mongo"]["ports"] == [f"{INTERNAL_BIND_ADDRESS}:${{DF_MONGO_PORT}}:27017"]


@mock.patch("deepfellow.server.utils.port_migration.save_compose_file")
@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_leaves_already_bound_install_untouched(
    mock_echo: Mock, mock_save_compose_file: Mock, tmp_path: Path
) -> None:
    services = {
        "server": {"ports": [f"{SERVER_BIND_ADDRESS}:${{DF_SERVER_PORT}}:8000"]},
        "mongo": {"ports": [f"{INTERNAL_BIND_ADDRESS}:${{DF_MONGO_PORT}}:27017"]},
        "etcd": {"expose": ["2379"]},
    }
    save_compose_file({"services": services}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME, quiet=True)

    result = migrate_port_bindings(tmp_path)

    assert result is False
    assert mock_echo.confirm.call_count == 0
    assert mock_save_compose_file.call_count == 0


@mock.patch("deepfellow.server.utils.port_migration.echo")
def test_migrate_port_bindings_only_binds_server_port_without_local_internal_services(
    mock_echo: Mock, tmp_path: Path
) -> None:
    save_compose_file(
        {"services": {"server": {"ports": ["${DF_SERVER_PORT}:8000"]}}},
        tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME,
        quiet=True,
    )

    result = migrate_port_bindings(tmp_path)

    assert result is False
    assert mock_echo.confirm.call_count == 0
    assert _services(tmp_path)["server"]["ports"] == [f"{SERVER_BIND_ADDRESS}:${{DF_SERVER_PORT}}:8000"]
