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

from deepfellow.common.exceptions import DockerNetworkError
from deepfellow.common.state import state
from deepfellow.update import _run_step, _uses_local_image, update


def test_run_step_returns_true_when_step_succeeds() -> None:
    step = Mock()

    result = _run_step(step)

    assert result is True
    assert step.call_count == 1


def test_run_step_returns_false_when_step_raises_typer_exit() -> None:
    step = Mock(side_effect=typer.Exit(1))

    result = _run_step(step)

    assert result is False


@mock.patch.object(state, "debug", True)
def test_run_step_returns_false_when_step_raises_in_debug_mode() -> None:
    step = Mock(side_effect=DockerNetworkError("network gone"))

    result = _run_step(step)

    assert result is False


@mock.patch("deepfellow.update.load_compose_file")
def test_uses_local_image_returns_true_when_pull_policy_never(mock_load_compose_file: Mock) -> None:
    mock_load_compose_file.return_value = {"services": {"infra": {"pull_policy": "never"}}}

    result = _uses_local_image(Path("/some/dir"), "infra")

    assert result is True


@mock.patch("deepfellow.update.load_compose_file")
def test_uses_local_image_returns_false_when_pull_policy_absent(mock_load_compose_file: Mock) -> None:
    mock_load_compose_file.return_value = {"services": {"infra": {}}}

    result = _uses_local_image(Path("/some/dir"), "infra")

    assert result is False


@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_runs_all_three_components_when_installed(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    server_dir = mock_get_server_dir.return_value
    server_dir.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    update()

    assert mock_update_cli.call_count == 1
    assert mock_update_infra.call_count == 1
    assert mock_update_infra.call_args == mock.call(
        directory=mock_infra_dir, image=mock.ANY, local_image=False, tag=None
    )
    assert mock_update_server.call_count == 1
    assert mock_update_server.call_args == mock.call(directory=server_dir, image=mock.ANY, local_image=False, tag=None)


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_skips_missing_infra_and_server(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = False
    mock_get_server_dir.return_value.is_dir.return_value = False

    update()

    assert mock_update_cli.call_count == 1
    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0
    assert mock_echo.info.call_count == 2


@mock.patch("deepfellow.update.echo")
@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_skips_infra_and_server_pinned_to_local_image(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {
        "services": {"infra": {"pull_policy": "never"}, "server": {"pull_policy": "never"}}
    }

    update()

    assert mock_update_cli.call_count == 1
    assert mock_update_infra.call_count == 0
    assert mock_update_server.call_count == 0
    assert mock_echo.info.call_count == 2


@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli", side_effect=typer.Exit(1))
def test_update_continues_to_infra_and_server_when_cli_update_fails(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    with pytest.raises(typer.Exit) as exc_info:
        update()

    assert exc_info.value.exit_code == 1
    assert mock_update_infra.call_count == 1
    assert mock_update_server.call_count == 1


@mock.patch("deepfellow.update.load_compose_file")
@mock.patch("deepfellow.update.get_default_server_directory")
@mock.patch("deepfellow.update.DF_INFRA_DIRECTORY")
@mock.patch("deepfellow.update.update_server")
@mock.patch("deepfellow.update.update_infra")
@mock.patch("deepfellow.update.update_cli")
def test_update_exits_zero_when_all_steps_succeed(
    mock_update_cli: Mock,
    mock_update_infra: Mock,
    mock_update_server: Mock,
    mock_infra_dir: Mock,
    mock_get_server_dir: Mock,
    mock_load_compose_file: Mock,
) -> None:
    mock_infra_dir.is_dir.return_value = True
    mock_get_server_dir.return_value.is_dir.return_value = True
    mock_load_compose_file.return_value = {"services": {}}

    update()
