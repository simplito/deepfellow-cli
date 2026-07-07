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

from deepfellow.cli.utils.command_resolver import resolve_cli_command
from deepfellow.common.config import read_env_file
from deepfellow.common.state import state

_UV_UPDATE_CMD = ["uv", "tool", "upgrade", "deepfellow-cli"]


def test_resolve_cli_command_reads_from_config_file(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("DF_UPDATE_COMMAND=uv tool upgrade deepfellow-cli\n")
    state.cli_config_file = config_file
    detect = Mock()

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == _UV_UPDATE_CMD
    assert detect.call_count == 0


def test_resolve_cli_command_falls_back_to_detection_when_config_missing(tmp_path: Path) -> None:
    state.cli_config_file = tmp_path / "nonexistent_config"
    detect = Mock(return_value=["pipx", "upgrade", "deepfellow-cli"])

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == ["pipx", "upgrade", "deepfellow-cli"]
    assert detect.call_count == 1


def test_resolve_cli_command_falls_back_when_config_has_no_key(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("DF_SERVER_URL=http://localhost:8000\n")
    state.cli_config_file = config_file
    detect = Mock(return_value=_UV_UPDATE_CMD)

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == _UV_UPDATE_CMD
    assert detect.call_count == 1


@mock.patch("deepfellow.cli.utils.command_resolver.echo")
def test_resolve_cli_command_falls_back_when_config_has_malformed_command(mock_echo: Mock, tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text('DF_UPDATE_COMMAND=uv "unmatched\n')
    state.cli_config_file = config_file
    detect = Mock(return_value=_UV_UPDATE_CMD)

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == _UV_UPDATE_CMD
    assert mock_echo.warning.call_count == 1
    assert detect.call_count == 1


def test_resolve_cli_command_self_heals_by_persisting_detected_command(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("DF_SERVER_URL=http://localhost:8000\n")
    state.cli_config_file = config_file
    detect = Mock(return_value=_UV_UPDATE_CMD)

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == _UV_UPDATE_CMD
    persisted = read_env_file(config_file)
    assert persisted["DF_UPDATE_COMMAND"] == "uv tool upgrade deepfellow-cli"


def test_resolve_cli_command_self_heal_creates_config_when_missing(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    state.cli_config_file = config_file
    detect = Mock(return_value=_UV_UPDATE_CMD)

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd == _UV_UPDATE_CMD
    persisted = read_env_file(config_file)
    assert persisted["DF_UPDATE_COMMAND"] == "uv tool upgrade deepfellow-cli"


def test_resolve_cli_command_returns_none_when_detection_fails(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    state.cli_config_file = config_file
    detect = Mock(return_value=None)

    cmd = resolve_cli_command("DF_UPDATE_COMMAND", detect)

    assert cmd is None
    assert not config_file.exists()
