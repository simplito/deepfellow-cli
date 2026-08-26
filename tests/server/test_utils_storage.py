# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server storage helpers."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from deepfellow.server.utils.storage import config_json_exists


@mock.patch("deepfellow.server.utils.storage.DF_SERVER_STORAGE_DIRECTORY")
def test_config_json_exists_returns_true_when_file_present(mock_storage_dir: Mock, tmp_path: Path) -> None:
    mock_storage_dir.__truediv__.side_effect = lambda name: tmp_path / name
    (tmp_path / "config.json").write_text("{}")

    result = config_json_exists()

    assert result is True


@mock.patch("deepfellow.server.utils.storage.DF_SERVER_STORAGE_DIRECTORY")
def test_config_json_exists_returns_false_when_file_absent(mock_storage_dir: Mock, tmp_path: Path) -> None:
    mock_storage_dir.__truediv__.side_effect = lambda name: tmp_path / name

    result = config_json_exists()

    assert result is False
