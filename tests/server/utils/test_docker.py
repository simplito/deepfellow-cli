# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock

import pytest
import typer

from deepfellow.common.docker import DockerError
from deepfellow.common.state import state
from deepfellow.server.utils.docker import start_server, stop_server


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
def test_stop_server_stops_compose_service(mock_run: mock.MagicMock, tmp_path: Path):
    stop_server(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "stop", "server"], cwd=tmp_path)
