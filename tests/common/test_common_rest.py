# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the rest module."""

from pathlib import Path
from unittest import mock

from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_calls_env_set_when_config_file_set_and_no_existing_server(mock_env_set, mock_check_health):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {}

    get_server_url("http://example.com")

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(
        Path("/fake/.env"), "SERVER_URL", "http://example.com", should_raise=False, docker_note=False
    )
