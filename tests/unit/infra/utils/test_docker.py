# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.common.docker import DockerError
from deepfellow.common.state import state
from deepfellow.infra.utils.docker import _startup_pull_images, start_infra, stop_infra

COMPOSE_UP = ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"]
STARTED_AT = "2026-10-26T10:00:00.123456789Z"
PULL_LOGS = (
    "INFO Starting DeepFellow Infra\n"
    "INFO Image 'ollama/ollama:0.34.1' not found locally. Pulling...\n"
    "INFO Image 'ollama/ollama:0.34.1' not found locally. Pulling...\n"
    "INFO Image 'easyocr/easyocr:1.0' not found locally. Pulling...\n"
)


@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_ensures_network_and_starts_compose(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_get_docker_network.return_value = "df_network"

    start_infra(tmp_path)

    assert mock_get_docker_network.call_count == 1
    assert mock_get_docker_network.call_args == mock.call(tmp_path)
    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == mock.call("df_network")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(COMPOSE_UP, cwd=tmp_path, raises=DockerError)


@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_exits_when_compose_fails_without_pulls(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = []

    with pytest.raises(typer.Exit):
        start_infra(tmp_path)

    assert mock_startup_pull_images.call_args == mock.call(tmp_path)
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to start DeepFellow Infra. See the Docker output above for details."
    )
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_reraises_compose_error_in_debug_mode(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(state, "debug", True)
    up_error = DockerError("compose failed")
    mock_run.side_effect = up_error
    mock_startup_pull_images.return_value = []

    with pytest.raises(DockerError) as exc_info:
        start_infra(tmp_path)

    assert exc_info.value is up_error
    assert mock_echo.error.call_args == mock.call("Failed to start DeepFellow Infra: compose failed")


@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_exits_when_compose_fails_and_infra_not_running(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1"]
    mock_is_service_running.return_value = False

    with pytest.raises(typer.Exit):
        start_infra(tmp_path)

    assert mock_is_service_running.call_args == mock.call("infra", tmp_path)
    assert mock_echo.error.call_count == 1
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.infra.utils.docker.time.sleep")
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.service_health")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_waits_until_healthy_when_infra_pulls_images(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_service_health: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1", "easyocr/easyocr:1.0"]
    mock_is_service_running.return_value = True
    mock_service_health.side_effect = ["unhealthy", "starting", "healthy"]

    start_infra(tmp_path)

    assert mock_service_health.call_count == 3
    assert mock_service_health.call_args == mock.call(tmp_path, "infra")
    assert mock_sleep.call_count == 2
    assert mock_echo.warning.call_count == 1
    assert "ollama/ollama:0.34.1, easyocr/easyocr:1.0" in mock_echo.warning.call_args.args[0]
    assert mock_echo.success.call_args == mock.call("DeepFellow Infra is up.")
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.docker.time.sleep")
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.service_health")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_exits_when_infra_stops_while_pulling(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_service_health: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1"]
    mock_is_service_running.side_effect = [True, True, False]
    mock_service_health.return_value = "unhealthy"

    with pytest.raises(typer.Exit):
        start_infra(tmp_path)

    assert mock_is_service_running.call_count == 3
    assert mock_sleep.call_count == 1
    assert mock_echo.error.call_count == 1
    assert "stopped while pulling" in mock_echo.error.call_args.args[0]
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.docker.INFRA_PULL_WAIT_TIMEOUT_SECONDS", 600)
@mock.patch("deepfellow.infra.utils.docker.time.monotonic")
@mock.patch("deepfellow.infra.utils.docker.time.sleep")
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.service_health")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_exits_when_pull_wait_times_out(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_service_health: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_monotonic: mock.MagicMock,
) -> None:
    directory = Path("/infra")
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1"]
    mock_is_service_running.return_value = True
    mock_service_health.return_value = "unhealthy"
    # Deadline set at 0 + 600; the first check is in time, the second is past it.
    mock_monotonic.side_effect = [0.0, 300.0, 600.0]

    with pytest.raises(typer.Exit):
        start_infra(directory)

    assert mock_sleep.call_count == 1
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "DeepFellow Infra isn't healthy after 10 minutes of pulling service images. Check `deepfellow infra logs`."
    )
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.docker.time.monotonic")
@mock.patch("deepfellow.infra.utils.docker.time.sleep")
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.service_health")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_reports_progress_periodically_while_pulling(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_service_health: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_monotonic: mock.MagicMock,
) -> None:
    directory = Path("/infra")
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1"]
    mock_is_service_running.return_value = True
    mock_service_health.side_effect = ["unhealthy"] * 5 + ["healthy"]
    # Start at 0, then one reading per unhealthy poll; reports are due at 60s and 120s.
    mock_monotonic.side_effect = [0.0, 30.0, 59.0, 65.0, 100.0, 130.0]

    start_infra(directory)

    assert mock_sleep.call_count == 5
    assert mock_echo.info.call_args_list == [
        mock.call("Still waiting for DeepFellow Infra to pull service images... (65s)"),
        mock.call("Still waiting for DeepFellow Infra to pull service images... (130s)"),
    ]
    assert mock_echo.success.call_args == mock.call("DeepFellow Infra is up.")


@mock.patch("deepfellow.infra.utils.docker.run")
def test_startup_pull_images_reads_logs_since_container_start(mock_run: mock.MagicMock, tmp_path: Path) -> None:
    mock_run.side_effect = ["abc123\n", f"{STARTED_AT}\n", PULL_LOGS]

    result = _startup_pull_images(tmp_path)

    assert result == ["ollama/ollama:0.34.1", "easyocr/easyocr:1.0"]
    assert mock_run.call_args_list == [
        mock.call(["docker", "compose", "ps", "-q", "infra"], cwd=tmp_path, capture_output=True, raises=DockerError),
        mock.call(
            ["docker", "inspect", "-f", "{{.State.StartedAt}}", "abc123"], capture_output=True, raises=DockerError
        ),
        mock.call(
            ["docker", "compose", "logs", "--no-log-prefix", "--since", STARTED_AT, "infra"],
            cwd=tmp_path,
            capture_output=True,
            raises=DockerError,
        ),
    ]


@pytest.mark.parametrize(
    ("side_effect", "expected_run_calls", "expected_debug_error"),
    [
        ([""], 1, None),
        (["abc123\n", DockerError("no such container")], 2, DockerError("no such container")),
        (["abc123\n", f"{STARTED_AT}\n", DockerError("no such service")], 3, DockerError("no such service")),
        (["abc123\n", f"{STARTED_AT}\n", "INFO Starting DeepFellow Infra\n"], 3, None),
    ],
    ids=["without_container", "start_time_unreadable", "logs_fail", "logs_have_no_pulls"],
)
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.run")
def test_startup_pull_images_returns_empty_list(
    mock_run: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
    side_effect: list[str | DockerError],
    expected_run_calls: int,
    expected_debug_error: DockerError | None,
) -> None:
    mock_run.side_effect = side_effect

    result = _startup_pull_images(tmp_path)

    assert result == []
    assert mock_run.call_count == expected_run_calls
    if expected_debug_error is None:
        assert mock_echo.debug.call_count == 0
    else:
        assert mock_echo.debug.call_count == 1
        assert str(mock_echo.debug.call_args[0][0]) == str(expected_debug_error)


@mock.patch("deepfellow.infra.utils.docker.run")
def test_stop_infra_stops_compose_service(mock_run: mock.MagicMock, tmp_path: Path) -> None:
    stop_infra(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "stop", "infra"], cwd=tmp_path)


@mock.patch("deepfellow.infra.utils.docker.time.sleep")
@mock.patch("deepfellow.infra.utils.docker.echo")
@mock.patch("deepfellow.infra.utils.docker.service_health")
@mock.patch("deepfellow.infra.utils.docker.is_service_running_or_raise")
@mock.patch("deepfellow.infra.utils.docker._startup_pull_images")
@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_keeps_waiting_when_docker_state_is_unknown_during_pull_wait(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_startup_pull_images: mock.MagicMock,
    mock_is_service_running: mock.MagicMock,
    mock_service_health: mock.MagicMock,
    mock_echo: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = DockerError(None)
    mock_startup_pull_images.return_value = ["ollama/ollama:0.34.1"]
    mock_is_service_running.side_effect = [True, DockerError("ps failed")]
    mock_service_health.side_effect = [None, "healthy"]

    start_infra(tmp_path)

    assert mock_sleep.call_count == 1
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 1
