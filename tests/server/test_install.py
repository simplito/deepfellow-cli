# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server install command."""

from unittest import mock

import pytest
import typer

from deepfellow.server.install import install


@mock.patch("deepfellow.server.install.ensure_directory")
@mock.patch("deepfellow.server.install.configure_otel")
@mock.patch("deepfellow.server.install.assert_docker")
@mock.patch("deepfellow.server.install.echo")
def test_install_otel_local_and_otel_url_are_mutually_exclusive(
    mock_echo, mock_assert_docker, mock_configure_otel, mock_ensure_directory
):
    with pytest.raises(typer.Exit) as exc_info:
        install(otel_local=True, otel_url="http://existing-otel:4317")

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--otel-local and --otel-url are mutually exclusive; pass only one.")
    assert mock_assert_docker.call_count == 0
    assert mock_configure_otel.call_count == 0
    assert mock_ensure_directory.call_count == 0
