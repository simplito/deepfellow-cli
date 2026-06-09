# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server options helpers."""

from pathlib import Path
from unittest import mock

from deepfellow.common.defaults import DF_SERVER_DIRECTORY
from deepfellow.common.state import state
from deepfellow.server.utils.options import (
    default_directory_callback,
    get_default_server_directory,
    set_default_server_directory,
)


@mock.patch("deepfellow.server.utils.options.env_get", return_value=None)
def test_get_default_server_directory_returns_default_when_unset(mock_env_get):
    state.cli_config_file = Path("/fake/config")

    result = get_default_server_directory()

    assert result == DF_SERVER_DIRECTORY
    assert mock_env_get.call_count == 1
    assert mock_env_get.call_args == mock.call(Path("/fake/config"), "DF_DEFAULT_SERVER_DIR", should_raise=False)


@mock.patch("deepfellow.server.utils.options.env_get", return_value="/srv/deepfellow")
def test_get_default_server_directory_returns_configured_path(mock_env_get):
    result = get_default_server_directory()

    assert result == Path("/srv/deepfellow")


@mock.patch("deepfellow.server.utils.options.env_set")
@mock.patch("deepfellow.server.utils.options.env_get")
def test_set_default_server_directory_force_always_writes(mock_env_get, mock_env_set):
    state.cli_config_file = Path("/fake/config")

    set_default_server_directory("/srv/new", force=True)

    assert mock_env_get.call_count == 0
    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(Path("/fake/config"), "DF_DEFAULT_SERVER_DIR", "/srv/new")


@mock.patch("deepfellow.server.utils.options.env_set")
@mock.patch("deepfellow.server.utils.options.env_get", return_value=None)
def test_set_default_server_directory_writes_when_no_existing_value(mock_env_get, mock_env_set):
    set_default_server_directory("/srv/new", force=False)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(state.cli_config_file, "DF_DEFAULT_SERVER_DIR", "/srv/new")


@mock.patch("deepfellow.server.utils.options.env_set")
@mock.patch("deepfellow.server.utils.options.env_get", return_value="/srv/existing")
def test_set_default_server_directory_skips_write_when_value_exists(mock_env_get, mock_env_set):
    set_default_server_directory("/srv/new", force=False)

    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.server.utils.options.env_get", return_value="/srv/configured")
def test_default_directory_callback_uses_configured_dir_when_none(mock_env_get):
    result = default_directory_callback(None)

    assert result == Path("/srv/configured").resolve()


@mock.patch("deepfellow.server.utils.options.env_get", return_value=None)
def test_default_directory_callback_falls_back_to_default_when_none_and_unset(mock_env_get):
    result = default_directory_callback(None)

    assert result == DF_SERVER_DIRECTORY.resolve()


def test_default_directory_callback_uses_provided_dir():
    result = default_directory_callback("relative/dir")

    assert result == Path("relative/dir").resolve()
