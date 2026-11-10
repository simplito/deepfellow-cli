# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.docker import DockerError
from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.workspace.utils.docker import (
    confirm_server_running,
    is_server_container_running,
    is_server_running,
    offer_restart,
    start_workspace,
    stop_workspace,
    workspace_running,
    workspace_url,
)

UP = ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"]


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.ensure_network")
@mock.patch("deepfellow.workspace.utils.docker.run")
def test_start_workspace_brings_stack_up(mock_run: Mock, mock_network: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    start_workspace(tmp_path)

    assert mock_run.call_args == mock.call(UP, cwd=tmp_path, raises=DockerError)


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.ensure_network")
@mock.patch("deepfellow.workspace.utils.docker.run")
def test_start_workspace_ensures_network_from_env_before_up(
    mock_run: Mock, mock_network: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text('DF_WORKSPACE_DOCKER_NETWORK="my-net"\n')
    calls = Mock()
    calls.attach_mock(mock_network, "network")
    calls.attach_mock(mock_run, "run")

    start_workspace(tmp_path)

    assert calls.mock_calls == [mock.call.network("my-net"), mock.call.run(UP, cwd=tmp_path, raises=DockerError)]


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.ensure_network")
@mock.patch("deepfellow.workspace.utils.docker.run")
def test_start_workspace_without_network_in_env_uses_default_network(
    mock_run: Mock, mock_network: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    start_workspace(tmp_path)

    assert mock_network.call_args == mock.call("deepfellow-infra-net")


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.ensure_network", side_effect=DockerNetworkError("boom"))
@mock.patch("deepfellow.workspace.utils.docker.run")
def test_start_workspace_network_failure_exits_without_starting(
    mock_run: Mock, mock_network: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        start_workspace(tmp_path)

    assert mock_run.call_count == 0
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.ensure_network")
@mock.patch("deepfellow.workspace.utils.docker.run", side_effect=DockerError)
def test_start_workspace_compose_failure_exits(
    mock_run: Mock, mock_network: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        start_workspace(tmp_path)

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.workspace.utils.docker.run", return_value="abc123\n")
def test_is_server_container_running_container_found_returns_true(mock_run: Mock) -> None:
    assert is_server_container_running() is True


@mock.patch("deepfellow.workspace.utils.docker.run", return_value="")
def test_is_server_container_running_no_container_returns_false(mock_run: Mock) -> None:
    assert is_server_container_running() is False


@mock.patch("deepfellow.workspace.utils.docker.run", side_effect=DockerError)
def test_is_server_container_running_docker_failure_returns_false(mock_run: Mock) -> None:
    assert is_server_container_running() is False


@mock.patch("deepfellow.workspace.utils.docker.is_server_reachable")
@mock.patch("deepfellow.workspace.utils.docker.is_server_container_running", return_value=True)
def test_is_server_running_local_container_skips_url_check(
    mock_container: Mock, mock_reachable: Mock, tmp_path: Path
) -> None:
    assert is_server_running(tmp_path) is True
    assert mock_reachable.call_count == 0


@mock.patch("deepfellow.workspace.utils.docker.is_server_reachable", return_value=True)
@mock.patch("deepfellow.workspace.utils.docker.is_server_container_running", return_value=False)
def test_is_server_running_remote_server_answers_returns_true(
    mock_container: Mock, mock_reachable: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text('DF_SERVER_URL="https://df.example.com/v1"\n')

    assert is_server_running(tmp_path) is True
    assert mock_reachable.call_args == mock.call("https://df.example.com/v1")


@mock.patch("deepfellow.workspace.utils.docker.is_server_reachable", return_value=False)
@mock.patch("deepfellow.workspace.utils.docker.is_server_container_running", return_value=False)
def test_is_server_running_remote_server_down_returns_false(
    mock_container: Mock, mock_reachable: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text('DF_SERVER_URL="https://df.example.com/v1"\n')

    assert is_server_running(tmp_path) is False


@mock.patch("deepfellow.workspace.utils.docker.is_server_reachable")
@mock.patch("deepfellow.workspace.utils.docker.is_server_container_running", return_value=False)
def test_is_server_running_no_container_and_no_url_returns_false(
    mock_container: Mock, mock_reachable: Mock, tmp_path: Path
) -> None:
    assert is_server_running(tmp_path) is False
    assert mock_reachable.call_count == 0


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.is_server_running", return_value=True)
def test_confirm_server_running_server_up_does_not_ask(mock_server: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    confirm_server_running(tmp_path)

    assert mock_echo.confirm.call_count == 0
    assert mock_server.call_args == mock.call(tmp_path)


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.is_server_running", return_value=False)
def test_confirm_server_running_server_down_declined_exits(mock_server: Mock, mock_echo: Mock, tmp_path: Path) -> None:
    mock_echo.confirm.return_value = False

    with pytest.raises(typer.Exit):
        confirm_server_running(tmp_path)


@mock.patch("deepfellow.workspace.utils.docker.echo")
@mock.patch("deepfellow.workspace.utils.docker.is_server_running", return_value=False)
def test_confirm_server_running_server_down_confirmed_goes_on(
    mock_server: Mock, mock_echo: Mock, tmp_path: Path
) -> None:
    mock_echo.confirm.return_value = True

    confirm_server_running(tmp_path)

    assert mock_echo.confirm.call_count == 1


def test_workspace_url_uses_port_and_bind_address_from_env(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text('DF_WORKSPACE_PORT="3100"\nDF_WORKSPACE_BIND_ADDRESS="127.0.0.1"\n')

    assert workspace_url(tmp_path) == "http://127.0.0.1:3100"


def test_workspace_url_without_env_uses_default_port(tmp_path: Path) -> None:
    assert workspace_url(tmp_path) == "http://localhost:3000"


@mock.patch("deepfellow.workspace.utils.docker.run")
def test_stop_workspace_stops_containers(mock_run: Mock, tmp_path: Path) -> None:
    stop_workspace(tmp_path)

    assert mock_run.call_args == mock.call(["docker", "compose", "stop"], cwd=tmp_path)


@pytest.mark.parametrize("running", [True, False])
@mock.patch("deepfellow.workspace.utils.docker.is_service_running_or_raise")
def test_workspace_running_returns_container_state(mock_is_running: Mock, running: bool, tmp_path: Path):
    mock_is_running.return_value = running

    result = workspace_running(tmp_path)

    assert result is running
    assert mock_is_running.call_args == mock.call("workspace", tmp_path)


@mock.patch("deepfellow.workspace.utils.docker.is_service_running_or_raise", side_effect=DockerError("no daemon"))
def test_workspace_running_returns_none_when_docker_cannot_tell(mock_is_running: Mock, tmp_path: Path):
    result = workspace_running(tmp_path)

    assert result is None


@mock.patch("deepfellow.workspace.utils.docker.workspace_url", return_value="http://localhost:3000")
@mock.patch("deepfellow.workspace.utils.docker.start_workspace")
@mock.patch("deepfellow.workspace.utils.docker.stop_workspace")
@mock.patch("deepfellow.workspace.utils.docker.confirm_server_running")
@mock.patch("deepfellow.workspace.utils.docker.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.utils.docker.echo")
def test_offer_restart_restarts_running_workspace_when_confirmed(
    mock_echo: Mock,
    mock_workspace_running: Mock,
    mock_confirm_server_running: Mock,
    mock_stop_workspace: Mock,
    mock_start_workspace: Mock,
    mock_workspace_url: Mock,
    tmp_path: Path,
):
    mock_echo.confirm.return_value = True
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_confirm_server_running, "confirm_server_running")
    _mock_manager.attach_mock(mock_stop_workspace, "stop")
    _mock_manager.attach_mock(mock_start_workspace, "start")

    offer_restart(tmp_path, "update")

    assert mock_echo.confirm.call_args == mock.call(
        "Restart DeepFellow Workspace now to apply the update?", default=True
    )
    assert _mock_manager.mock_calls == [
        mock.call.confirm_server_running(tmp_path),
        mock.call.stop(tmp_path),
        mock.call.start(tmp_path),
    ]
    assert mock_echo.info.call_args == mock.call("DeepFellow Workspace restarted on http://localhost:3000")


@pytest.mark.parametrize(("no_restart", "answer"), [(False, False), (True, True)])
@mock.patch("deepfellow.workspace.utils.docker.start_workspace")
@mock.patch("deepfellow.workspace.utils.docker.stop_workspace")
@mock.patch("deepfellow.workspace.utils.docker.workspace_running", return_value=True)
@mock.patch("deepfellow.workspace.utils.docker.echo")
def test_offer_restart_declined_or_skipped_points_at_workspace_restart(
    mock_echo: Mock,
    mock_workspace_running: Mock,
    mock_stop_workspace: Mock,
    mock_start_workspace: Mock,
    no_restart: bool,
    answer: bool,
    tmp_path: Path,
):
    mock_echo.confirm.return_value = answer

    offer_restart(tmp_path, "change", no_restart)

    assert mock_echo.confirm.call_count == (0 if no_restart else 1)
    assert mock_stop_workspace.call_count == 0
    assert mock_start_workspace.call_count == 0
    assert mock_echo.info.call_args == mock.call("Run 'workspace restart' to apply the change.")


@mock.patch("deepfellow.workspace.utils.docker.start_workspace")
@mock.patch("deepfellow.workspace.utils.docker.workspace_running", return_value=False)
@mock.patch("deepfellow.workspace.utils.docker.echo")
def test_offer_restart_leaves_stopped_workspace_stopped(
    mock_echo: Mock, mock_workspace_running: Mock, mock_start_workspace: Mock, tmp_path: Path
):
    offer_restart(tmp_path, "update")

    assert mock_echo.confirm.call_count == 0
    assert mock_start_workspace.call_count == 0
    assert mock_echo.info.call_args == mock.call(
        "DeepFellow Workspace is not running; the update applies on the next 'workspace start'."
    )


@mock.patch("deepfellow.workspace.utils.docker.start_workspace")
@mock.patch("deepfellow.workspace.utils.docker.workspace_running", return_value=None)
@mock.patch("deepfellow.workspace.utils.docker.echo")
def test_offer_restart_warns_when_docker_cannot_tell(
    mock_echo: Mock, mock_workspace_running: Mock, mock_start_workspace: Mock, tmp_path: Path
):
    offer_restart(tmp_path, "change")

    assert mock_echo.confirm.call_count == 0
    assert mock_start_workspace.call_count == 0
    assert "Could not check" in str(mock_echo.warning.call_args.args[0])
