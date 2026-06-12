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
from unittest.mock import Mock

import pytest
import typer

from deepfellow.infra.disconnect import disconnect


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_check_infra_directory(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((directory,), {})


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_raises_exit_when_service_not_running(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = False

    with pytest.raises(typer.Exit):
        disconnect(directory=directory)


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_env_get(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    disconnect(directory=directory)

    assert mock_env_get.call_count == 1
    assert mock_env_get.call_args == ((directory / ".env", "DF_CONNECT_TO_MESH_URL"), {})


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_error_when_not_connected(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    disconnect(directory=directory)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == (("Already disconnected",), {})


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_does_not_call_env_set_when_not_connected(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = None

    disconnect(directory=directory)

    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_success_when_not_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == (("Operation ends with no changes.",), {})


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_does_not_call_run_when_not_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = False

    disconnect(directory=directory)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_env_set_for_mesh_url_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock.call(directory / ".env", "DF_CONNECT_TO_MESH_URL", "") in mock_env_set.call_args_list


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_env_set_for_mesh_key_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock.call(directory / ".env", "DF_CONNECT_TO_MESH_KEY", "") in mock_env_set.call_args_list


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_docker_compose_down_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock.call(["docker", "compose", "down"], cwd=directory, quiet=True) in mock_run.call_args_list


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_docker_compose_up_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert (
        mock.call(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory, quiet=True)
        in mock_run.call_args_list
    )


@mock.patch("deepfellow.infra.disconnect.run")
@mock.patch("deepfellow.infra.disconnect.env_set")
@mock.patch("deepfellow.infra.disconnect.env_get")
@mock.patch("deepfellow.infra.disconnect.echo")
@mock.patch("deepfellow.infra.disconnect.is_service_running")
@mock.patch("deepfellow.infra.disconnect.check_infra_directory")
def test_disconnect_calls_echo_success_when_confirmed(
    mock_check: Mock,
    mock_is_running: Mock,
    mock_echo: Mock,
    mock_env_get: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    directory: Path,
) -> None:
    mock_is_running.return_value = True
    mock_env_get.return_value = "http://parent-infra:8086"
    mock_echo.confirm.return_value = True

    disconnect(directory=directory)

    assert mock_echo.success.call_count == 1
    assert "http://parent-infra:8086" in mock_echo.success.call_args[0][0]
