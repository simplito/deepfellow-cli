# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import subprocess
from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.common.docker import DockerError
from deepfellow.common.state import state
from deepfellow.server.utils.docker import (
    NIGHTSHIFT_NOT_INSTALLED_HINT,
    _nightshift_should_be_up,
    _nightshift_should_stay_down,
    _service_health,
    assert_nightshift_installed,
    has_nightshift_service,
    print_nightshift_status,
    reconcile_nightshift_running_state,
    restart_nightshift,
    service_running_or_exit,
    start_nightshift,
    start_server,
    stop_nightshift,
    stop_server,
    wait_for_docker,
    wait_for_service_running,
)


@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_ensures_network_and_starts_compose(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
):
    mock_get_docker_network.return_value = "df_network"

    start_server(tmp_path)

    assert mock_get_docker_network.call_count == 1
    assert mock_get_docker_network.call_args == mock.call(tmp_path)
    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == mock.call("df_network")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=tmp_path, raises=DockerError
    )


@mock.patch("deepfellow.server.utils.docker.volume_exists", return_value=True)
@mock.patch("deepfellow.server.utils.docker.resolve_compose_volume_name", return_value="server_mongo")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_mongo_auth_hint_when_logs_show_authentication_failure(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
):
    mock_run.side_effect = [
        DockerError("dependency failed to start: container server is unhealthy"),
        "pymongo.errors.OperationFailure: Authentication failed.",
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 2
    assert mock_run.call_args_list[1] == mock.call(
        ["docker", "compose", "logs", "--tail", "200", "server"], cwd=tmp_path, capture_output=True, raises=DockerError
    )
    assert mock_resolve_volume.call_count == 1
    assert mock_resolve_volume.call_args == mock.call(tmp_path, "mongo")
    assert mock_volume_exists.call_count == 1
    assert mock_volume_exists.call_args == mock.call("server_mongo")
    assert mock_echo.error.call_count == 1
    assert "MongoDB" in mock_echo.error.call_args.args[0]
    assert "docker volume rm server_mongo" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.resolve_compose_volume_name", return_value=None)
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_credential_hint_when_volume_name_unresolvable(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    tmp_path: Path,
):
    mock_run.side_effect = [
        DockerError("dependency failed to start: container server is unhealthy"),
        "pymongo.errors.OperationFailure: Authentication failed.",
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_echo.error.call_count == 1
    assert "docker volume rm" not in mock_echo.error.call_args.args[0]
    assert "Check the DF_MONGO_* credentials in .env" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.volume_exists", return_value=False)
@mock.patch("deepfellow.server.utils.docker.resolve_compose_volume_name", return_value="server_mongo")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_does_not_blame_volume_when_resolved_name_does_not_exist(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
):
    # e.g. a custom/external MongoDB (--mongodb-url): the compose-scoped name still resolves
    # (it's purely synthetic), but no such volume was ever created, so it must not be blamed.
    mock_run.side_effect = [
        DockerError("dependency failed to start: container server is unhealthy"),
        "pymongo.errors.OperationFailure: Authentication failed.",
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_volume_exists.call_count == 1
    assert mock_volume_exists.call_args == mock.call("server_mongo")
    assert mock_echo.error.call_count == 1
    assert "docker volume rm" not in mock_echo.error.call_args.args[0]
    assert "Check the DF_MONGO_* credentials in .env" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_error_when_logs_do_not_show_authentication_failure(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    # docker compose up's own output is never captured, so a real DockerError from it carries no
    # stderr of its own - str(DockerError(None)) == "None" is what run() actually produces here.
    mock_run.side_effect = [
        DockerError(None),
        "server  | some unrelated startup error",
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_does_not_report_mongo_hint_on_unrelated_authentication_failure(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    # "Authentication failed" alone (e.g. an unrelated Infra API key rejection) must not match -
    # only pymongo's specific OperationFailure alongside it should trigger the Mongo-specific hint.
    mock_run.side_effect = [
        DockerError(None),
        "server  | Infra API key rejected: Authentication failed.",
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_error_when_fetching_logs_fails(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    logs_error = DockerError("docker: command not found")
    mock_run.side_effect = [DockerError(None), logs_error]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )
    assert mock_echo.debug.call_count == 1
    assert mock_echo.debug.call_args == mock.call(logs_error)


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_exception_detail_when_docker_error_carries_a_message(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    # e.g. an OSError from a missing docker binary, converted to DockerError(str(exc_info))
    mock_run.side_effect = DockerError("docker: command not found")

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 2
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Failed to start DeepFellow Server: docker: command not found")


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reraises_original_error_in_debug_mode(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
):
    state.debug = True
    up_error = DockerError("docker: command not found")
    mock_run.side_effect = [up_error, DockerError("docker: command not found")]

    with pytest.raises(DockerError) as exc_info:
        start_server(tmp_path)

    assert exc_info.value is up_error


@mock.patch("deepfellow.server.utils.docker.run")
def test_service_health_returns_status_from_compose_ps(mock_run: mock.MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = "unhealthy\n"

    result = _service_health(tmp_path, "nightshift")

    assert result == "unhealthy"
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "ps", "nightshift", "--format", "{{.Health}}"],
        cwd=tmp_path,
        capture_output=True,
        raises=DockerError,
    )


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
def test_service_health_returns_none_when_compose_ps_fails(
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    ps_error = DockerError("docker: command not found")
    mock_run.side_effect = ps_error

    result = _service_health(tmp_path, "nightshift")

    assert result is None
    assert mock_echo.debug.call_count == 1
    assert mock_echo.debug.call_args == mock.call(ps_error)


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_nightshift_unhealthy_hint_when_server_healthy(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_has_nightshift_service.return_value = True
    mock_run.side_effect = [DockerError(None), "server  | Application startup complete.", "healthy\n", "unhealthy\n"]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 4
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "compose", "ps", "server", "--format", "{{.Health}}"],
        cwd=tmp_path,
        capture_output=True,
        raises=DockerError,
    )
    assert mock_run.call_args_list[3] == mock.call(
        ["docker", "compose", "ps", "nightshift", "--format", "{{.Health}}"],
        cwd=tmp_path,
        capture_output=True,
        raises=DockerError,
    )
    assert mock_echo.error.call_count == 1
    assert "Nightshift worker failed its healthcheck" in mock_echo.error.call_args.args[0]
    hints = " ".join(call.args[0] for call in mock_echo.info.call_args_list)
    assert "RabbitMQ" in hints
    assert "`rabbitmq` section of the server's config.json" in hints
    assert "docker compose logs nightshift" in hints
    assert "deepfellow server config get" in hints
    assert "deepfellow server config set" in hints
    assert "server.workers.healthcheck" in hints


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_error_when_nightshift_healthy(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_has_nightshift_service.return_value = True
    mock_run.side_effect = [DockerError(None), "server  | some unrelated startup error", "healthy\n", "healthy\n"]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 4
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )


# "unhealthy" - the server is running but failed its own healthcheck (e.g. a broken config.json),
# "starting" - it hasn't passed it yet, "" - it isn't running at all. Nightshift is then unhealthy
# because of the server, not RabbitMQ, so its health isn't even checked.
@pytest.mark.parametrize("server_health", ["unhealthy\n", "starting\n", ""])
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_error_when_server_not_healthy(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    tmp_path: Path,
    server_health: str,
) -> None:
    mock_has_nightshift_service.return_value = True
    mock_run.side_effect = [DockerError(None), "server  | some unrelated startup error", server_health]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 3
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "compose", "ps", "server", "--format", "{{.Health}}"],
        cwd=tmp_path,
        capture_output=True,
        raises=DockerError,
    )
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_generic_error_when_nightshift_health_unknown(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_has_nightshift_service.return_value = True
    mock_run.side_effect = [
        DockerError(None),
        "server  | some unrelated startup error",
        "healthy\n",
        DockerError("ps failed"),
    ]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 4
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Server. See the Docker output above for details."
    )


@mock.patch("deepfellow.server.utils.docker.resolve_compose_volume_name", return_value=None)
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reports_mongo_auth_hint_before_nightshift_hint(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    mock_resolve_compose_volume_name: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_has_nightshift_service.return_value = True
    mock_run.side_effect = [DockerError(None), "pymongo.errors.OperationFailure: Authentication failed."]

    with pytest.raises(typer.Exit):
        start_server(tmp_path)

    assert mock_run.call_count == 2
    assert mock_has_nightshift_service.call_count == 0
    assert mock_echo.error.call_count == 1
    assert "MongoDB" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_reraises_original_error_in_debug_mode_when_nightshift_unhealthy(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_has_nightshift_service: mock.MagicMock,
    tmp_path: Path,
) -> None:
    state.debug = True
    mock_has_nightshift_service.return_value = True
    up_error = DockerError(None)
    mock_run.side_effect = [up_error, "server  | Application startup complete.", "healthy\n", "unhealthy\n"]

    with pytest.raises(DockerError) as exc_info:
        start_server(tmp_path)

    assert exc_info.value is up_error
    assert mock_run.call_count == 4
    assert mock_echo.error.call_count == 1
    assert "Nightshift worker failed its healthcheck" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.run")
def test_stop_server_stops_compose_service(mock_run: mock.MagicMock, tmp_path: Path):
    stop_server(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "stop", "server"], cwd=tmp_path)


@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_nightshift_uses_up_dash_d_no_deps_scoped_to_nightshift_only(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
):
    mock_get_docker_network.return_value = "df_network"

    start_nightshift(tmp_path)

    assert mock_ensure_network.call_args == mock.call("df_network")
    assert mock_run.call_count == 1
    # No `raises=DockerError` (unlike start_server()'s own call) - nothing catches a DockerError
    # here, so passing it would let a docker failure escape uncaught with a raw traceback instead
    # of run()'s own clean echo.error + reraise_if_debug() default handling.
    assert mock_run.call_args == mock.call(["docker", "compose", "up", "-d", "--no-deps", "nightshift"], cwd=tmp_path)


@mock.patch("deepfellow.server.utils.docker.run")
def test_stop_nightshift_stops_only_nightshift_service(mock_run: mock.MagicMock, tmp_path: Path):
    stop_nightshift(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "stop", "nightshift"], cwd=tmp_path)


@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
def test_restart_nightshift_stops_then_starts(
    mock_stop_nightshift: mock.MagicMock, mock_start_nightshift: mock.MagicMock, tmp_path: Path
):
    restart_nightshift(tmp_path)

    assert mock_stop_nightshift.call_count == 1
    assert mock_start_nightshift.call_count == 1


@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict", return_value={"df_nightshift_mode": "always"})
def test_nightshift_should_stay_down_false_when_mode_always(mock_read_env: mock.MagicMock, tmp_path: Path):
    assert _nightshift_should_stay_down(tmp_path) is False


@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "", "df_nightshift_stop": ""},
)
def test_nightshift_should_stay_down_false_when_hours_missing(mock_read_env: mock.MagicMock, tmp_path: Path):
    assert _nightshift_should_stay_down(tmp_path) is False


@mock.patch("deepfellow.server.utils.docker.is_within_shift_window", return_value=False)
@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "22:00", "df_nightshift_stop": "06:00"},
)
def test_nightshift_should_stay_down_true_when_shift_and_outside_window(
    mock_read_env: mock.MagicMock, mock_is_within_window: mock.MagicMock, tmp_path: Path
):
    assert _nightshift_should_stay_down(tmp_path) is True
    assert mock_is_within_window.call_args == mock.call("22:00", "06:00")


@mock.patch("deepfellow.server.utils.docker.is_within_shift_window", return_value=True)
@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "22:00", "df_nightshift_stop": "06:00"},
)
def test_nightshift_should_stay_down_false_when_shift_and_within_window(
    mock_read_env: mock.MagicMock, mock_is_within_window: mock.MagicMock, tmp_path: Path
):
    assert _nightshift_should_stay_down(tmp_path) is False


@mock.patch("deepfellow.server.utils.docker._nightshift_should_stay_down", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_scales_nightshift_to_zero_when_it_should_stay_down(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_should_stay_down: mock.MagicMock,
    tmp_path: Path,
):
    """Nightshift must never be started at all when it's outside its shift window - not started
    and then immediately stopped back down, which would be pointless and could let it briefly pick
    up a task before being killed."""
    start_server(tmp_path)

    assert mock_run.call_args == mock.call(
        ["docker", "compose", "up", "-d", "--wait", "--remove-orphans", "--scale", "nightshift=0"],
        cwd=tmp_path,
        raises=DockerError,
    )
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.server.utils.docker._nightshift_should_stay_down", return_value=False)
@mock.patch("deepfellow.server.utils.docker.run")
@mock.patch("deepfellow.server.utils.docker.ensure_network")
@mock.patch("deepfellow.server.utils.docker.get_docker_network")
def test_start_server_does_not_scale_when_nightshift_should_run(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_should_stay_down: mock.MagicMock,
    tmp_path: Path,
):
    start_server(tmp_path)

    assert mock_run.call_args == mock.call(
        ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=tmp_path, raises=DockerError
    )


@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict", return_value={"df_nightshift_mode": "always"})
def test_nightshift_should_be_up_true_when_mode_always(mock_read_env: mock.MagicMock, tmp_path: Path):
    assert _nightshift_should_be_up(tmp_path) is True


@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "", "df_nightshift_stop": ""},
)
def test_nightshift_should_be_up_true_when_hours_missing(mock_read_env: mock.MagicMock, tmp_path: Path):
    assert _nightshift_should_be_up(tmp_path) is True


@mock.patch("deepfellow.server.utils.docker.is_within_shift_window", return_value=True)
@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "22:00", "df_nightshift_stop": "06:00"},
)
def test_nightshift_should_be_up_matches_shift_window(
    mock_read_env: mock.MagicMock, mock_is_within_window: mock.MagicMock, tmp_path: Path
):
    assert _nightshift_should_be_up(tmp_path) is True
    assert mock_is_within_window.call_args == mock.call("22:00", "06:00")


@mock.patch("deepfellow.server.utils.docker.is_within_shift_window", side_effect=ValueError)
@mock.patch(
    "deepfellow.server.utils.docker.read_env_file_to_dict",
    return_value={"df_nightshift_mode": "shift", "df_nightshift_start": "bad", "df_nightshift_stop": "06:00"},
)
def test_nightshift_should_be_up_true_when_schedule_malformed(
    mock_read_env: mock.MagicMock, mock_is_within_window: mock.MagicMock, tmp_path: Path
):
    """A hand-edited/corrupted .env bypasses the CLI's own HH:MM validation - falls back to the
    same conservative "up" default as a missing schedule, instead of crashing every
    start_server()/status call."""
    assert _nightshift_should_be_up(tmp_path) is True


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit")
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_starts_when_should_be_up_but_is_down(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    mock_is_running.side_effect = lambda service, directory: service == "server"

    reconcile_nightshift_running_state(tmp_path)

    assert mock_start.call_args == mock.call(tmp_path)
    assert mock_stop.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit")
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_starts_when_server_is_running(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    mock_is_running.side_effect = lambda service, directory: service == "server"

    reconcile_nightshift_running_state(tmp_path)

    assert mock_start.call_args == mock.call(tmp_path)


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.wait_for_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=False)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_starts_once_server_comes_up_within_the_wait(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_wait: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    """After boot, the timer waits for Docker's restart policy to bring `server` back."""
    reconcile_nightshift_running_state(tmp_path, server_wait_seconds=120)

    assert mock_wait.call_args == mock.call("server", tmp_path, 120)
    assert mock_start.call_args == mock.call(tmp_path)


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.wait_for_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=False)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_does_not_start_when_server_never_comes_up_within_the_wait(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_wait: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    reconcile_nightshift_running_state(tmp_path, server_wait_seconds=120)

    assert mock_wait.call_args == mock.call("server", tmp_path, 120)
    assert mock_start.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=False)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_does_not_start_when_server_is_not_running(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    """A timer firing on a stack that was stopped on purpose must not bring part of it back up."""
    reconcile_nightshift_running_state(tmp_path)

    assert mock_start.call_count == 0
    assert mock_stop.call_count == 0
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=True)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=False)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_stops_the_worker_outside_its_window_even_without_the_server(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    reconcile_nightshift_running_state(tmp_path)

    assert mock_stop.call_args == mock.call(tmp_path)
    assert mock_start.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=True)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=False)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_stops_when_should_be_down_but_is_up(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    reconcile_nightshift_running_state(tmp_path)

    assert mock_stop.call_count == 1
    assert mock_start.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=True)
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=True)
@mock.patch("deepfellow.server.utils.docker.echo")
def test_reconcile_running_state_does_nothing_when_already_correct(
    mock_echo: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
):
    """The whole point - never restart an already-correctly-running worker, which would
    interrupt whatever task it's mid-processing for nothing."""
    reconcile_nightshift_running_state(tmp_path)

    assert mock_start.call_count == 0
    assert mock_stop.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.print_docker_status")
@mock.patch("deepfellow.server.utils.docker.is_service_running", return_value=False)
@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.docker.echo")
def test_print_nightshift_status_shift_mode_down_shows_mode_and_status(
    mock_echo: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_print_docker_status: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_read_env.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    print_nightshift_status(tmp_path)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "nightshift mode: shift (start 22:00, stop 06:00)" in info_messages
    assert "nightshift status: down" in info_messages
    # is_service_running() already told us it's down - no point also asking docker for live
    # stats/ps on a container that isn't there, which print_docker_status() would otherwise
    # surface as a cascade of confusing errors ("invalid container name or ID: value is empty").
    assert mock_print_docker_status.call_count == 0


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.print_docker_status")
@mock.patch("deepfellow.server.utils.docker.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.docker.echo")
def test_print_nightshift_status_shift_mode_up_shows_mode_and_status(
    mock_echo: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_print_docker_status: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_read_env.return_value = {
        "df_nightshift_mode": "shift",
        "df_nightshift_start": "22:00",
        "df_nightshift_stop": "06:00",
    }

    print_nightshift_status(tmp_path)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "nightshift mode: shift (start 22:00, stop 06:00)" in info_messages
    assert "nightshift status: up" in info_messages
    assert mock_print_docker_status.call_args == mock.call(tmp_path, "nightshift")


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.utils.docker.print_docker_status")
@mock.patch("deepfellow.server.utils.docker.is_service_running", return_value=True)
@mock.patch("deepfellow.server.utils.docker.read_env_file_to_dict")
@mock.patch("deepfellow.server.utils.docker.echo")
def test_print_nightshift_status_always_mode_shows_no_schedule(
    mock_echo: mock.MagicMock,
    mock_read_env: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_print_docker_status: mock.MagicMock,
    mock_has_nightshift: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_read_env.return_value = {"df_nightshift_mode": "always"}

    print_nightshift_status(tmp_path)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "nightshift mode: always" in info_messages
    assert "nightshift status: up" in info_messages
    assert not any("start" in msg or "stop" in msg for msg in info_messages)


@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.run")
def test_wait_for_docker_returns_true_immediately_when_docker_answers(
    mock_run: mock.MagicMock, mock_sleep: mock.MagicMock
):
    assert wait_for_docker(300) is True

    assert mock_run.call_count == 1
    assert mock_sleep.call_count == 0


@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.run")
def test_wait_for_docker_retries_until_the_daemon_comes_up(mock_run: mock.MagicMock, mock_sleep: mock.MagicMock):
    """Right after boot the scheduled action can fire before the daemon is up."""
    mock_run.side_effect = [DockerError("down"), DockerError("down"), None]

    assert wait_for_docker(300, poll_interval_seconds=5) is True

    assert mock_run.call_count == 3
    assert mock_sleep.call_args_list == [mock.call(5), mock.call(5)]


@mock.patch("deepfellow.server.utils.docker.time.monotonic", side_effect=[0, 10, 301])
@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.run", side_effect=DockerError("down"))
def test_wait_for_docker_returns_false_when_the_daemon_never_answers(
    mock_run: mock.MagicMock, mock_sleep: mock.MagicMock, mock_monotonic: mock.MagicMock
):
    assert wait_for_docker(300) is False

    assert mock_run.call_count == 2


@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=True)
def test_wait_for_service_running_returns_true_immediately_when_running(
    mock_is_running: mock.MagicMock, mock_sleep: mock.MagicMock, tmp_path: Path
):
    assert wait_for_service_running("server", tmp_path, 120) is True

    assert mock_is_running.call_args == mock.call("server", tmp_path)
    assert mock_sleep.call_count == 0


@mock.patch("deepfellow.server.utils.docker.time.monotonic", side_effect=[0, 10, 20])
@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", side_effect=[False, False, True])
def test_wait_for_service_running_retries_until_the_service_comes_up(
    mock_is_running: mock.MagicMock, mock_sleep: mock.MagicMock, mock_monotonic: mock.MagicMock, tmp_path: Path
):
    """Right after boot Docker answers before its restart policy has brought the stack back."""
    assert wait_for_service_running("server", tmp_path, 120, poll_interval_seconds=5) is True

    assert mock_is_running.call_count == 3
    assert mock_sleep.call_args_list == [mock.call(5), mock.call(5)]


@mock.patch("deepfellow.server.utils.docker.time.monotonic", side_effect=[0, 10, 121])
@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=False)
def test_wait_for_service_running_returns_false_when_the_service_never_comes_up(
    mock_is_running: mock.MagicMock, mock_sleep: mock.MagicMock, mock_monotonic: mock.MagicMock, tmp_path: Path
):
    assert wait_for_service_running("server", tmp_path, 120) is False

    assert mock_is_running.call_count == 2


@mock.patch("deepfellow.server.utils.docker.time.sleep")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit", return_value=False)
def test_wait_for_service_running_checks_once_with_zero_timeout(
    mock_is_running: mock.MagicMock, mock_sleep: mock.MagicMock, tmp_path: Path
):
    assert wait_for_service_running("server", tmp_path, 0) is False

    assert mock_is_running.call_count == 1
    assert mock_sleep.call_count == 0


@mock.patch("deepfellow.common.system.subprocess.run")
def test_wait_for_docker_works_through_the_real_run_helper(mock_subprocess_run: mock.MagicMock):
    """run() refuses `quiet=True` together with `capture_output=True` (SystemError) - a mocked run()
    can't catch that, so exercise the real one with only subprocess.run mocked."""
    mock_subprocess_run.return_value = subprocess.CompletedProcess(["docker", "info"], 0, stdout="", stderr="")

    assert wait_for_docker(0) is True


@mock.patch("deepfellow.common.system.subprocess.run")
def test_wait_for_docker_gives_up_through_the_real_run_helper(mock_subprocess_run: mock.MagicMock):
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(1, ["docker", "info"], stderr="daemon down")

    assert wait_for_docker(0) is False


@pytest.mark.parametrize(
    ("compose", "expected"),
    [
        ("services:\n  server: {}\n  nightshift: {}\n", True),
        ("services:\n  server: {}\n", False),
        (None, False),
    ],
)
def test_has_nightshift_service_reads_the_installs_compose_file(tmp_path: Path, compose: str | None, expected: bool):
    if compose is not None:
        (tmp_path / "compose.yaml").write_text(compose)

    assert has_nightshift_service(tmp_path) is expected


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=False)
def test_assert_nightshift_installed_exits_with_a_hint_when_the_service_is_missing(
    mock_has_nightshift: mock.MagicMock, mock_echo: mock.MagicMock, tmp_path: Path
):
    with pytest.raises(typer.Exit) as exc_info:
        assert_nightshift_installed(tmp_path)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call(NIGHTSHIFT_NOT_INSTALLED_HINT)


@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
def test_assert_nightshift_installed_passes_when_the_service_exists(
    mock_has_nightshift: mock.MagicMock, tmp_path: Path
):
    assert_nightshift_installed(tmp_path)


@pytest.mark.parametrize("running", [True, False])
@mock.patch("deepfellow.server.utils.docker.is_service_running_or_raise")
def test_service_running_or_exit_returns_what_docker_reports(
    mock_is_running: mock.MagicMock, running: bool, tmp_path: Path
):
    mock_is_running.return_value = running

    assert service_running_or_exit("server", tmp_path) is running
    assert mock_is_running.call_args == mock.call("server", cwd=tmp_path)


@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.is_service_running_or_raise", side_effect=DockerError("daemon is down"))
def test_service_running_or_exit_stops_instead_of_reading_a_failed_check_as_not_running(
    mock_is_running: mock.MagicMock, mock_echo: mock.MagicMock, tmp_path: Path
):
    with pytest.raises(typer.Exit) as exc_info:
        service_running_or_exit("server", tmp_path)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert "daemon is down" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.service_running_or_exit")
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=False)
def test_reconcile_running_state_is_a_noop_when_the_install_has_no_nightshift_service(
    mock_has_nightshift: mock.MagicMock,
    mock_running: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    tmp_path: Path,
):
    reconcile_nightshift_running_state(tmp_path)

    assert mock_running.call_count == 0
    assert mock_start.call_count == 0
    assert mock_stop.call_count == 0


@mock.patch("deepfellow.server.utils.docker.start_nightshift")
@mock.patch("deepfellow.server.utils.docker.stop_nightshift")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.is_service_running_or_raise", side_effect=DockerError("ps failed"))
@mock.patch("deepfellow.server.utils.docker._nightshift_should_be_up", return_value=False)
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=True)
def test_reconcile_running_state_fails_instead_of_acting_on_a_failed_state_check(
    mock_has_nightshift: mock.MagicMock,
    mock_should_be_up: mock.MagicMock,
    mock_is_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_stop: mock.MagicMock,
    mock_start: mock.MagicMock,
    tmp_path: Path,
):
    """A failing `docker compose ps` is not "worker not running" - starting or stopping on that guess
    could leave the worker in the wrong state."""
    with pytest.raises(typer.Exit):
        reconcile_nightshift_running_state(tmp_path)

    assert mock_start.call_count == 0
    assert mock_stop.call_count == 0


@mock.patch("deepfellow.server.utils.docker.print_docker_status")
@mock.patch("deepfellow.server.utils.docker.is_service_running")
@mock.patch("deepfellow.server.utils.docker.echo")
@mock.patch("deepfellow.server.utils.docker.has_nightshift_service", return_value=False)
def test_print_nightshift_status_says_not_installed_when_the_install_has_no_nightshift_service(
    mock_has_nightshift: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_print_docker_status: mock.MagicMock,
    tmp_path: Path,
):
    print_nightshift_status(tmp_path)

    assert mock_echo.info.call_count == 1
    assert "not installed" in mock_echo.info.call_args.args[0]
    assert mock_is_service_running.call_count == 0
    assert mock_print_docker_status.call_count == 0


def test_nightshift_not_installed_hint_points_at_update_and_install():
    assert "deepfellow server update" in NIGHTSHIFT_NOT_INSTALLED_HINT
    assert "deepfellow server install" in NIGHTSHIFT_NOT_INSTALLED_HINT
    assert "before Nightshift existed" not in NIGHTSHIFT_NOT_INSTALLED_HINT
