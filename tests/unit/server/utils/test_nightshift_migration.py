# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.defaults import (
    DF_RABBITMQ_URL,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_RABBITMQ,
    DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS,
    NIGHTSHIFT_FEATURES,
)
from deepfellow.common.docker import load_compose_file, save_compose_file
from deepfellow.common.state import state
from deepfellow.server.utils.configure import NightshiftConfig
from deepfellow.server.utils.nightshift import SHIFT_WITHOUT_HOURS_WARNING
from deepfellow.server.utils.nightshift_migration import (
    add_nightshift_to_install,
    resolve_nightshift_addition,
    warn_nightshift_declined,
)

LOCAL_RABBITMQ = NightshiftConfig(
    envs={"DF_RABBITMQ_URL": DF_RABBITMQ_URL, "DF_RABBITMQ_USER": "gen-user", "DF_RABBITMQ_PASSWORD": "gen-password"},
    docker_compose=DOCKER_COMPOSE_RABBITMQ,
)
EXTERNAL_RABBITMQ = NightshiftConfig(
    envs={"DF_RABBITMQ_URL": "mq.example:5672", "DF_RABBITMQ_USER": "df", "DF_RABBITMQ_PASSWORD": "secret"},
    docker_compose={},
)
SERVER_BASE_ENVS = ["DF_MONGO_URL=${DF_MONGO_URL}", "DF_LOG_LEVEL=${DF_LOG_LEVEL}"]
OTEL_ENVS = ["DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}"]


def _old_server_service(**overrides: object) -> dict:
    return {
        "image": "${DF_SERVER_IMAGE}",
        "environment": [*SERVER_BASE_ENVS, *OTEL_ENVS],
        "volumes": [
            "/home/u/.deepfellow/server/storage:/app/storage",
            "/home/u/.deepfellow/server/plugins:/app/plugins",
        ],
        "networks": ["deepfellow-infra-net"],
        "depends_on": {"mongo": {"condition": "service_healthy"}, "otel-collector": {"condition": "service_started"}},
        **overrides,
    }


@pytest.fixture
def install_directory(tmp_path: Path) -> Path:
    save_compose_file(
        {"services": {"server": _old_server_service(), "mongo": {"image": "mongo"}}, "volumes": {"mongo_data": None}},
        tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME,
    )
    save_env_file(tmp_path / ".env", {"DF_SERVER_PORT": "8000"})
    return tmp_path


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=True)
def test_resolve_nightshift_addition_returns_none_when_nightshift_present(
    mock_has_nightshift_service: mock.MagicMock, mock_echo: mock.MagicMock, directory: Path
):
    result = resolve_nightshift_addition(directory, True, "mq.example:5672", "df", "secret")

    assert result is None
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.error.call_count == 0


@pytest.mark.parametrize(
    ("rabbitmq_url", "rabbitmq_username", "rabbitmq_password"),
    [
        ("mq.example:5672", "", ""),
        (None, "df", ""),
        (None, "", "secret"),
    ],
)
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_rejects_no_nightshift_with_rabbitmq_options(
    mock_has_nightshift_service: mock.MagicMock,
    rabbitmq_url: str | None,
    rabbitmq_username: str,
    rabbitmq_password: str,
    directory: Path,
):
    with pytest.raises(typer.BadParameter):
        resolve_nightshift_addition(directory, False, rabbitmq_url, rabbitmq_username, rabbitmq_password)


@pytest.mark.parametrize("non_interactive", [False, True])
@mock.patch("deepfellow.server.utils.nightshift_migration.is_custom_rabbitmq")
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
@mock.patch.object(state, "yes", True)
def test_resolve_nightshift_addition_yes_returns_local_without_prompts(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_custom_rabbitmq: mock.MagicMock,
    non_interactive: bool,
    directory: Path,
):
    state.non_interactive = non_interactive

    result = resolve_nightshift_addition(directory, None, None, "", "")

    assert result == NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always", **LOCAL_RABBITMQ.envs}, docker_compose=DOCKER_COMPOSE_RABBITMQ
    )
    assert mock_local_rabbitmq_envs.call_args == mock.call("", "", {})
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.choice.call_count == 0
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_is_custom_rabbitmq.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
@mock.patch.object(state, "yes", True)
def test_resolve_nightshift_addition_no_nightshift_wins_over_yes(
    mock_has_nightshift_service: mock.MagicMock, mock_echo: mock.MagicMock, directory: Path
):
    result = resolve_nightshift_addition(directory, False, None, "", "")

    assert result is None
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.external_rabbitmq_envs", return_value=EXTERNAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
@mock.patch.object(state, "yes", True)
def test_resolve_nightshift_addition_rabbitmq_url_wins_over_yes(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_external_rabbitmq_envs: mock.MagicMock,
    directory: Path,
):
    result = resolve_nightshift_addition(directory, None, "mq.example:5672", "df", "secret")

    assert result is not None
    assert result.docker_compose == {}
    assert mock_external_rabbitmq_envs.call_args == mock.call("mq.example:5672", "df", "secret", {})


@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_rabbitmq_url_equal_to_default_means_local(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    directory: Path,
):
    result = resolve_nightshift_addition(directory, None, DF_RABBITMQ_URL, "", "")

    assert result is not None
    assert result.docker_compose == DOCKER_COMPOSE_RABBITMQ
    assert mock_local_rabbitmq_envs.call_count == 1


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
@mock.patch.object(state, "non_interactive", True)
def test_resolve_nightshift_addition_non_interactive_without_yes_exits(
    mock_has_nightshift_service: mock.MagicMock, mock_echo: mock.MagicMock, directory: Path
):
    with pytest.raises(typer.Exit) as exc_info:
        resolve_nightshift_addition(directory, None, None, "", "")

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    message = mock_echo.error.call_args.args[0]
    assert all(feature in message for feature in NIGHTSHIFT_FEATURES)
    assert all(option in message for option in ("--nightshift", "--rabbitmq-url", "--no-nightshift"))
    assert "`deepfellow server update`" in message


@pytest.mark.parametrize(("rabbitmq_username", "rabbitmq_password"), [("df", "secret"), ("df", ""), ("", "secret")])
@mock.patch("deepfellow.server.utils.nightshift_migration.is_custom_rabbitmq", return_value=False)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
@mock.patch.object(state, "non_interactive", True)
def test_resolve_nightshift_addition_rabbitmq_credentials_imply_nightshift(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_custom_rabbitmq: mock.MagicMock,
    rabbitmq_username: str,
    rabbitmq_password: str,
    directory: Path,
) -> None:
    result = resolve_nightshift_addition(directory, None, None, rabbitmq_username, rabbitmq_password)

    assert result is not None
    assert mock_echo.error.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert mock_local_rabbitmq_envs.call_args == mock.call(rabbitmq_username, rabbitmq_password, {})


@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_interactive_no_returns_none(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    directory: Path,
):
    mock_echo.confirm.return_value = False

    result = resolve_nightshift_addition(directory, None, None, "", "")

    assert result is None
    assert mock_echo.confirm.call_count == 1
    assert mock_read_env_file_to_dict.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.is_custom_rabbitmq", return_value=False)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_interactive_yes_local(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_custom_rabbitmq: mock.MagicMock,
    directory: Path,
):
    mock_echo.confirm.return_value = True

    result = resolve_nightshift_addition(directory, None, None, "", "")

    assert result is not None
    assert result.docker_compose == DOCKER_COMPOSE_RABBITMQ
    assert mock_is_custom_rabbitmq.call_args == mock.call(DF_RABBITMQ_URL)
    assert mock_local_rabbitmq_envs.call_count == 1


@mock.patch("deepfellow.server.utils.nightshift_migration.is_custom_rabbitmq", return_value=True)
@mock.patch("deepfellow.server.utils.nightshift_migration.external_rabbitmq_envs", return_value=EXTERNAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_interactive_yes_external(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_external_rabbitmq_envs: mock.MagicMock,
    mock_is_custom_rabbitmq: mock.MagicMock,
    directory: Path,
):
    mock_echo.confirm.return_value = True

    result = resolve_nightshift_addition(directory, None, None, "", "")

    assert result is not None
    assert result.docker_compose == {}
    assert mock_external_rabbitmq_envs.call_args == mock.call(DF_RABBITMQ_URL, "", "", {})


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.is_custom_rabbitmq")
@mock.patch("deepfellow.server.utils.nightshift_migration.external_rabbitmq_envs", return_value=EXTERNAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_uses_rabbitmq_from_env(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_external_rabbitmq_envs: mock.MagicMock,
    mock_is_custom_rabbitmq: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
):
    original_env = {"df_rabbitmq_url": "mq.example:5672", "df_rabbitmq_user": "df", "df_rabbitmq_password": "secret"}
    mock_read_env_file_to_dict.return_value = original_env

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.docker_compose == {}
    assert mock_read_env_file_to_dict.call_args == mock.call(directory / ".env")
    assert mock_external_rabbitmq_envs.call_args == mock.call("mq.example:5672", "df", "secret", original_env)
    assert mock_is_custom_rabbitmq.call_count == 0
    assert mock_echo.warning.call_count == 1
    message = mock_echo.warning.call_args.args[0]
    assert "mq.example:5672" in message
    assert f"--rabbitmq-url {DF_RABBITMQ_URL}" in message


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_rabbitmq_url_overrides_env_without_warning(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    mock_read_env_file_to_dict.return_value = {"df_rabbitmq_url": "mq.example:5672"}

    result = resolve_nightshift_addition(directory, None, DF_RABBITMQ_URL, "", "")

    assert result is not None
    assert result.docker_compose == DOCKER_COMPOSE_RABBITMQ
    assert mock_local_rabbitmq_envs.call_count == 1
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.external_rabbitmq_envs")
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_empty_env_rabbitmq_url_means_local(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_external_rabbitmq_envs: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    mock_read_env_file_to_dict.return_value = {"df_rabbitmq_url": ""}

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.docker_compose == DOCKER_COMPOSE_RABBITMQ
    assert mock_local_rabbitmq_envs.call_count == 1
    assert mock_external_rabbitmq_envs.call_count == 0
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_env_rabbitmq_alone_doesnt_add(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = {"df_rabbitmq_url": "mq.example:5672"}
    mock_echo.confirm.return_value = False

    result = resolve_nightshift_addition(directory, None, None, "", "")

    assert result is None


@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict", return_value={})
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_sets_mode_always_when_missing(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    directory: Path,
):
    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "always"
    assert "DF_NIGHTSHIFT_START" not in result.envs


@mock.patch("deepfellow.server.utils.nightshift_migration.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.nightshift_migration.is_user_manager_reachable", return_value=True)
@mock.patch("deepfellow.server.utils.nightshift_migration.is_systemd_available", return_value=True)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_keeps_shift_mode_from_env(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_systemd_available: mock.MagicMock,
    mock_is_user_manager_reachable: mock.MagicMock,
    mock_ensure_linger_enabled: mock.MagicMock,
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "shift"
    assert result.envs["DF_NIGHTSHIFT_START"] == "22:00"
    assert result.envs["DF_NIGHTSHIFT_STOP"] == "06:00"
    assert mock_is_systemd_available.call_count == 1
    assert mock_is_user_manager_reachable.call_count == 1
    assert mock_ensure_linger_enabled.call_count == 1


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.nightshift_migration.is_user_manager_reachable", return_value=False)
@mock.patch("deepfellow.server.utils.nightshift_migration.is_systemd_available", return_value=True)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_falls_back_to_always_without_user_session(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_systemd_available: mock.MagicMock,
    mock_is_user_manager_reachable: mock.MagicMock,
    mock_ensure_linger_enabled: mock.MagicMock,
    mock_echo: mock.MagicMock,
    directory: Path,
) -> None:
    mock_read_env_file_to_dict.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "always"
    assert "DF_NIGHTSHIFT_START" not in result.envs
    assert mock_ensure_linger_enabled.call_count == 0
    assert mock_echo.warning.call_count == 1
    assert "deepfellow server nightshift mode shift" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.server.utils.nightshift_migration.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.nightshift_migration.is_systemd_available", return_value=True)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_keeps_shift_mode_without_hours_and_skips_linger(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_systemd_available: mock.MagicMock,
    mock_ensure_linger_enabled: mock.MagicMock,
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = {"df_nightshift_mode": "shift"}

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "shift"
    assert result.envs["DF_NIGHTSHIFT_START"] == ""
    assert mock_ensure_linger_enabled.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.ensure_linger_enabled")
@mock.patch("deepfellow.server.utils.nightshift_migration.is_systemd_available", return_value=False)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_falls_back_to_always_without_systemd(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_systemd_available: mock.MagicMock,
    mock_ensure_linger_enabled: mock.MagicMock,
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "always"
    assert mock_echo.warning.call_count == 1
    assert mock_ensure_linger_enabled.call_count == 0


@pytest.mark.parametrize(
    "original_env",
    [
        {"df_nightshift_mode": "sometimes"},
        {"df_nightshift_mode": "shift", "df_nightshift_start": "25:00", "df_nightshift_stop": "06:00"},
    ],
)
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_falls_back_to_always_on_invalid_mode(
    mock_has_nightshift_service: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    original_env: dict[str, str],
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = original_env

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "always"
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_nightshift_question_lists_all_features(
    mock_has_nightshift_service: mock.MagicMock, mock_echo: mock.MagicMock, directory: Path
):
    mock_echo.confirm.return_value = False

    resolve_nightshift_addition(directory, None, None, "", "")

    question = mock_echo.confirm.call_args.args[0]
    assert all(feature in question for feature in NIGHTSHIFT_FEATURES)
    assert mock_echo.confirm.call_args.kwargs == {"default": True}


@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_warn_nightshift_declined_lists_features_and_next_steps(mock_echo: mock.MagicMock):
    warn_nightshift_declined()

    assert mock_echo.warning.call_count == 1
    message = mock_echo.warning.call_args.args[0]
    assert all(feature in message for feature in NIGHTSHIFT_FEATURES)
    assert "`deepfellow server update --nightshift`" in message
    assert "--rabbitmq-url" in message
    assert "deepfellow server install" in message


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_local_adds_rabbitmq_service_volume_and_depends_on(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, install_directory: Path
):
    config = NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always", **LOCAL_RABBITMQ.envs}, docker_compose=DOCKER_COMPOSE_RABBITMQ
    )

    add_nightshift_to_install(install_directory, config)

    compose = load_compose_file(install_directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    services = compose["services"]
    assert services["rabbitmq"]["image"] == DOCKER_COMPOSE_RABBITMQ["rabbitmq"]["image"]
    assert services["rabbitmq"]["networks"] == ["deepfellow-infra-net"]
    assert services["nightshift"]["networks"] == ["deepfellow-infra-net"]
    assert compose["volumes"] == {"mongo_data": None, "rabbitmq_data": None}
    assert services["server"]["depends_on"]["rabbitmq"] == {"condition": "service_healthy"}
    assert services["nightshift"]["depends_on"] == {
        "mongo": {"condition": "service_healthy"},
        "rabbitmq": {"condition": "service_healthy"},
    }
    assert set(DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS) <= set(services["server"]["environment"])
    assert services["mongo"] == {"image": "mongo"}
    env = read_env_file(install_directory / ".env")
    assert env["DF_SERVER_PORT"] == "8000"
    assert env["DF_RABBITMQ_URL"] == DF_RABBITMQ_URL
    assert env["DF_RABBITMQ_USER"] == "gen-user"
    assert env["DF_NIGHTSHIFT_MODE"] == "always"
    assert mock_echo.success.call_count == 1
    assert "deepfellow server config set" in mock_echo.info.call_args.args[0]


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_external_adds_no_rabbitmq_service(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, install_directory: Path
):
    config = NightshiftConfig(envs={"DF_NIGHTSHIFT_MODE": "always", **EXTERNAL_RABBITMQ.envs}, docker_compose={})

    add_nightshift_to_install(install_directory, config)

    compose = load_compose_file(install_directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    services = compose["services"]
    assert "rabbitmq" not in services
    assert "rabbitmq_data" not in compose["volumes"]
    assert "rabbitmq" not in services["server"]["depends_on"]
    assert "rabbitmq" not in services["nightshift"]["depends_on"]
    assert read_env_file(install_directory / ".env")["DF_RABBITMQ_URL"] == "mq.example:5672"
    assert "mq.example:5672" in mock_echo.success.call_args.args[0]


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_builds_nightshift_from_server_service(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, install_directory: Path
) -> None:
    config = NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always", **LOCAL_RABBITMQ.envs}, docker_compose=DOCKER_COMPOSE_RABBITMQ
    )

    add_nightshift_to_install(install_directory, config)

    nightshift = load_compose_file(install_directory / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]["nightshift"]
    assert nightshift["environment"] == [
        *SERVER_BASE_ENVS,
        *OTEL_ENVS,
        *DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS,
        "DF_NIGHTSHIFT_METRICS_HOST=0.0.0.0",
    ]
    assert nightshift["volumes"] == ["/home/u/.deepfellow/server/storage:/app/storage"]
    assert nightshift["networks"] == ["deepfellow-infra-net"]
    assert nightshift["depends_on"] == {
        "mongo": {"condition": "service_healthy"},
        "rabbitmq": {"condition": "service_healthy"},
    }
    assert "pull_policy" not in nightshift


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_doesnt_duplicate_server_rabbitmq_envs(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, tmp_path: Path
) -> None:
    server = _old_server_service(environment=[*SERVER_BASE_ENVS, *DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS])
    save_compose_file({"services": {"server": server}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)
    config = NightshiftConfig(envs={"DF_NIGHTSHIFT_MODE": "always", **EXTERNAL_RABBITMQ.envs}, docker_compose={})

    add_nightshift_to_install(tmp_path, config)

    environment = load_compose_file(tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]["server"]["environment"]
    assert environment == [*SERVER_BASE_ENVS, *DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS]


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule", side_effect=typer.Exit(1))
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_leaves_compose_unchanged_when_schedule_fails(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, install_directory: Path
) -> None:
    compose_file = install_directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose_before = load_compose_file(compose_file)
    config = NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "shift", "DF_NIGHTSHIFT_START": "22:00", "DF_NIGHTSHIFT_STOP": "06:00"}
        | LOCAL_RABBITMQ.envs,
        docker_compose=DOCKER_COMPOSE_RABBITMQ,
    )

    with pytest.raises(typer.Exit):
        add_nightshift_to_install(install_directory, config)

    assert load_compose_file(compose_file) == compose_before
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_keeps_local_image_pull_policy(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, tmp_path: Path
):
    save_compose_file(
        {"services": {"server": _old_server_service(pull_policy="never")}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME
    )
    config = NightshiftConfig(envs={"DF_NIGHTSHIFT_MODE": "always", **EXTERNAL_RABBITMQ.envs}, docker_compose={})

    add_nightshift_to_install(tmp_path, config)

    nightshift = load_compose_file(tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]["nightshift"]
    assert nightshift["pull_policy"] == "never"


@pytest.mark.parametrize(
    ("mode_envs", "expected_call"),
    [
        ({"DF_NIGHTSHIFT_MODE": "always"}, ("always", "", "")),
        (
            {"DF_NIGHTSHIFT_MODE": "shift", "DF_NIGHTSHIFT_START": "22:00", "DF_NIGHTSHIFT_STOP": "06:00"},
            ("shift", "22:00", "06:00"),
        ),
    ],
)
@mock.patch("deepfellow.server.utils.nightshift_migration.remove_nightshift_timers")
@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_reconciles_schedule(
    mock_echo: mock.MagicMock,
    mock_reconcile_nightshift_schedule: mock.MagicMock,
    mock_remove_nightshift_timers: mock.MagicMock,
    mode_envs: dict[str, str],
    expected_call: tuple[str, str, str],
    install_directory: Path,
):
    config = NightshiftConfig(envs={**mode_envs, **EXTERNAL_RABBITMQ.envs}, docker_compose={})

    add_nightshift_to_install(install_directory, config)

    assert mock_reconcile_nightshift_schedule.call_count == 1
    assert mock_reconcile_nightshift_schedule.call_args == mock.call(install_directory, *expected_call)
    assert mock_remove_nightshift_timers.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.remove_nightshift_timers")
@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_shift_without_hours_removes_timers_and_warns(
    mock_echo: mock.MagicMock,
    mock_reconcile_nightshift_schedule: mock.MagicMock,
    mock_remove_nightshift_timers: mock.MagicMock,
    install_directory: Path,
):
    config = NightshiftConfig(
        envs={
            "DF_NIGHTSHIFT_MODE": "shift",
            "DF_NIGHTSHIFT_START": "",
            "DF_NIGHTSHIFT_STOP": "",
            **EXTERNAL_RABBITMQ.envs,
        },
        docker_compose={},
    )

    add_nightshift_to_install(install_directory, config)

    assert mock_remove_nightshift_timers.call_args == mock.call(install_directory)
    assert mock_reconcile_nightshift_schedule.call_count == 0
    assert mock_echo.warning.call_args == mock.call(SHIFT_WITHOUT_HOURS_WARNING)


@mock.patch("deepfellow.server.utils.nightshift_migration.is_systemd_available")
@mock.patch("deepfellow.server.utils.nightshift_migration.local_rabbitmq_envs", return_value=LOCAL_RABBITMQ)
@mock.patch("deepfellow.server.utils.nightshift_migration.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.nightshift_migration.has_nightshift_service", return_value=False)
def test_resolve_nightshift_addition_keeps_always_mode_from_env(
    mock_has_nightshift_service: mock.MagicMock,
    mock_read_env_file_to_dict: mock.MagicMock,
    mock_local_rabbitmq_envs: mock.MagicMock,
    mock_is_systemd_available: mock.MagicMock,
    directory: Path,
):
    mock_read_env_file_to_dict.return_value = {"df_nightshift_mode": "always"}

    result = resolve_nightshift_addition(directory, True, None, "", "")

    assert result is not None
    assert result.envs["DF_NIGHTSHIFT_MODE"] == "always"
    assert mock_is_systemd_available.call_count == 0


@mock.patch("deepfellow.server.utils.nightshift_migration.reconcile_nightshift_schedule")
@mock.patch("deepfellow.server.utils.nightshift_migration.echo")
def test_add_nightshift_to_install_local_without_server_networks(
    mock_echo: mock.MagicMock, mock_reconcile_nightshift_schedule: mock.MagicMock, tmp_path: Path
):
    server = _old_server_service()
    del server["networks"]
    save_compose_file({"services": {"server": server}}, tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)
    config = NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always", **LOCAL_RABBITMQ.envs}, docker_compose=DOCKER_COMPOSE_RABBITMQ
    )

    add_nightshift_to_install(tmp_path, config)

    services = load_compose_file(tmp_path / DOCKER_COMPOSE_CONFIG_FILENAME)["services"]
    assert "networks" not in services["rabbitmq"]
    assert "networks" not in services["nightshift"]
