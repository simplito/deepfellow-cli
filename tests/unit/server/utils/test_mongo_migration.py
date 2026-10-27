# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.defaults import DOCKER_COMPOSE_CONFIG_FILENAME, DOCKER_COMPOSE_MONGO_DB, MONGO_DB_INIT_SH
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.server.utils.mongo_migration import (
    INIT_MONGO_SH_VOLUME,
    MongoMigrationError,
    is_legacy_mongo_install,
    migrate_mongo_to_app_user,
)

LEGACY_ENV = {
    "DF_MONGO_USER": "legacyroot",
    "DF_MONGO_PASSWORD": "legacypw",
    "DF_MONGO_DB": "deepfellow",
    "DF_INFRA_DOCKER_SUBNET": "deepfellow-infra-net",
}
NEW_MONGO_ENVS = [
    "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_INITDB_ROOT_USERNAME}",
    "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_INITDB_ROOT_PASSWORD}",
    "DF_MONGO_USER=${DF_MONGO_USER}",
    "DF_MONGO_PASSWORD=${DF_MONGO_PASSWORD}",
    "DF_MONGO_DB=${DF_MONGO_DB}",
]
MONGOSH = ["docker", "compose", "exec", "-T", "mongo", "mongosh", "--quiet"]


def _legacy_mongo_service() -> dict:
    return {
        "image": "mongo:8",
        "volumes": ["mongo:/data/db"],
        "environment": [
            "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_USER}",
            "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_PASSWORD}",
            "GLIBC_TUNABLES=glibc.cpu.hwcaps=-SHSTK",
        ],
    }


@pytest.fixture
def legacy_directory(tmp_path: Path) -> Path:
    save_compose_file(
        {"services": {"server": {"image": "server"}, "mongo": _legacy_mongo_service()}, "volumes": {"mongo": None}},
        tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME,
    )
    save_env_file(tmp_path / ".env", LEGACY_ENV)
    return tmp_path


def _mongosh_scripts(mock_run: mock.MagicMock) -> list[str]:
    return [call.kwargs["input"] for call in mock_run.call_args_list if call.args[0] == MONGOSH]


def test_is_legacy_mongo_install_true_for_root_mapped_to_server_account(legacy_directory: Path):
    result = is_legacy_mongo_install(legacy_directory)

    assert result is True


def test_is_legacy_mongo_install_false_for_new_install(tmp_path: Path):
    save_compose_file({"services": dict(DOCKER_COMPOSE_MONGO_DB)}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)

    result = is_legacy_mongo_install(tmp_path)

    assert result is False


def test_is_legacy_mongo_install_false_for_external_mongo(tmp_path: Path):
    save_compose_file({"services": {"server": {"image": "server"}}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)

    result = is_legacy_mongo_install(tmp_path)

    assert result is False


def test_is_legacy_mongo_install_false_without_compose_file(tmp_path: Path):
    result = is_legacy_mongo_install(tmp_path)

    assert result is False


@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.ensure_network")
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_switches_env_to_new_account(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    legacy_directory: Path,
):
    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is True
    assert read_env_file(legacy_directory / ".env") == {
        **LEGACY_ENV,
        "DF_MONGO_INITDB_ROOT_USERNAME": "legacyroot",
        "DF_MONGO_INITDB_ROOT_PASSWORD": "legacypw",
        "DF_MONGO_USER": "appuser1",
        "DF_MONGO_PASSWORD": "apppassword1",
    }
    assert mock_ensure_network.call_count == 0


@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_creates_then_verifies_read_write_account(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    legacy_directory: Path,
):
    migrate_mongo_to_app_user(legacy_directory)

    create_script, verify_script = _mongosh_scripts(mock_run)
    assert mock_run.call_count == 2
    assert "process.env.MONGO_INITDB_ROOT_USERNAME, process.env.MONGO_INITDB_ROOT_PASSWORD" in create_script
    assert (
        'createUser({"user": "appuser1", "pwd": "apppassword1", "roles": [{"role": "readWrite", "db": "deepfellow"}]})'
        in create_script
    )
    assert 'auth("appuser1", "apppassword1")' in verify_script
    assert 'getSiblingDB("deepfellow").getCollectionNames()' in verify_script
    assert all("quit(1)" in script for script in (create_script, verify_script))


@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_keeps_secrets_out_of_command_arguments(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    legacy_directory: Path,
):
    migrate_mongo_to_app_user(legacy_directory)

    arguments = [argument for call in mock_run.call_args_list for argument in call.args[0]]
    assert all(secret not in arguments for secret in ("legacypw", "apppassword1"))


@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_updates_compose_like_new_install(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    legacy_directory: Path,
):
    migrate_mongo_to_app_user(legacy_directory)

    mongo = load_compose_file(legacy_directory / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]["mongo"]
    assert mongo["environment"] == ["GLIBC_TUNABLES=glibc.cpu.hwcaps=-SHSTK", *NEW_MONGO_ENVS]
    assert mongo["volumes"] == ["mongo:/data/db", INIT_MONGO_SH_VOLUME]
    assert (legacy_directory / "init-mongo.sh").read_text() == MONGO_DB_INIT_SH
    assert (legacy_directory / "init-mongo.sh").stat().st_mode & 0o777 == 0o755
    assert is_legacy_mongo_install(legacy_directory) is False


@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.ensure_network")
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_starts_and_stops_mongo_when_not_running(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    legacy_directory: Path,
):
    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is True
    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == mock.call("deepfellow-infra-net")
    assert [call.args[0] for call in mock_run.call_args_list] == [
        ["docker", "compose", "up", "-d", "--wait", "mongo"],
        MONGOSH,
        MONGOSH,
        ["docker", "compose", "stop", "mongo"],
    ]


@pytest.mark.parametrize(
    ("failing_call", "expected_run_calls"),
    [
        (0, 1),
        (1, 2),
    ],
    ids=("create", "verify"),
)
@mock.patch("deepfellow.server.utils.mongo_migration.echo")
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_leaves_install_unchanged_on_mongosh_failure(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    failing_call: int,
    expected_run_calls: int,
    legacy_directory: Path,
):
    side_effect: list[object] = [None, None]
    side_effect[failing_call] = MongoMigrationError("Authentication failed.")
    mock_run.side_effect = side_effect
    env_before = (legacy_directory / ".env").read_text()
    compose_before = (legacy_directory / DOCKER_COMPOSE_CONFIG_FILENAME).read_text()

    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is False
    assert mock_run.call_count == expected_run_calls
    assert (legacy_directory / ".env").read_text() == env_before
    assert (legacy_directory / DOCKER_COMPOSE_CONFIG_FILENAME).read_text() == compose_before
    assert not (legacy_directory / "init-mongo.sh").exists()
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.mongo_migration.echo")
@mock.patch("deepfellow.server.utils.mongo_migration.ensure_network")
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_stops_started_mongo_on_failure(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_echo: mock.MagicMock,
    legacy_directory: Path,
):
    mock_run.side_effect = [None, MongoMigrationError("Authentication failed."), None]

    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is False
    assert mock_run.call_args_list[-1].args[0] == ["docker", "compose", "stop", "mongo"]


@mock.patch("deepfellow.server.utils.mongo_migration.echo")
@mock.patch("deepfellow.server.utils.mongo_migration.generate_password", side_effect=["appuser1", "apppassword1"])
@mock.patch("deepfellow.server.utils.mongo_migration.ensure_network")
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_switches_even_when_stopping_mongo_fails(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_generate_password: mock.MagicMock,
    mock_echo: mock.MagicMock,
    legacy_directory: Path,
):
    mock_run.side_effect = [None, None, None, MongoMigrationError("stop failed")]

    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is True
    assert read_env_file(legacy_directory / ".env")["DF_MONGO_USER"] == "appuser1"
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.mongo_migration.echo")
@mock.patch("deepfellow.server.utils.mongo_migration.ensure_network", side_effect=DockerNetworkError("no network"))
@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_returns_false_on_network_error(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_echo: mock.MagicMock,
    legacy_directory: Path,
):
    env_before = (legacy_directory / ".env").read_text()

    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is False
    assert mock_run.call_count == 0
    assert (legacy_directory / ".env").read_text() == env_before
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.mongo_migration.is_service_running")
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_only_finishes_compose_after_interrupted_run(
    mock_run: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    legacy_directory: Path,
):
    save_env_file(
        legacy_directory / ".env",
        {
            "DF_MONGO_INITDB_ROOT_USERNAME": "legacyroot",
            "DF_MONGO_INITDB_ROOT_PASSWORD": "legacypw",
            "DF_MONGO_USER": "appuser1",
            "DF_MONGO_PASSWORD": "apppassword1",
        },
    )
    env_before = (legacy_directory / ".env").read_text()

    result = migrate_mongo_to_app_user(legacy_directory)

    assert result is True
    assert mock_run.call_count == 0
    assert mock_is_service_running.call_count == 0
    assert (legacy_directory / ".env").read_text() == env_before
    assert is_legacy_mongo_install(legacy_directory) is False


@mock.patch("deepfellow.server.utils.mongo_migration.echo")
@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_skips_when_env_lacks_credentials(
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    save_compose_file({"services": {"mongo": _legacy_mongo_service()}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)
    save_env_file(tmp_path / ".env", {"DF_MONGO_USER": "legacyroot", "DF_MONGO_DB": "deepfellow"})

    result = migrate_mongo_to_app_user(tmp_path)

    assert result is False
    assert mock_run.call_count == 0
    assert mock_echo.warning.call_count == 1
    assert "DF_MONGO_PASSWORD" in mock_echo.warning.call_args.args[0]
    assert is_legacy_mongo_install(tmp_path) is True


@mock.patch("deepfellow.server.utils.mongo_migration.run")
def test_migrate_mongo_to_app_user_does_not_duplicate_init_mongo_mount(
    mock_run: mock.MagicMock,
    tmp_path: Path,
):
    mongo = {**_legacy_mongo_service(), "volumes": ["mongo:/data/db", INIT_MONGO_SH_VOLUME]}
    save_compose_file({"services": {"mongo": mongo}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)
    save_env_file(tmp_path / ".env", {**LEGACY_ENV, "DF_MONGO_INITDB_ROOT_USERNAME": "legacyroot"})

    migrate_mongo_to_app_user(tmp_path)

    volumes = load_compose_file(tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]["mongo"]["volumes"]
    assert volumes == ["mongo:/data/db", INIT_MONGO_SH_VOLUME]
