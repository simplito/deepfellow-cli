# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the suite install command."""

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.suite.install import install as install_command


@pytest.fixture
def default_install_kwargs() -> dict:
    return {
        "admin_name": "Admin",
        "admin_email": "admin@example.com",
        "admin_password": "Sup3r$ecret!",
    }


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_delegates_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(**default_install_kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**default_install_kwargs)


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_translates_install_error_to_exit(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(**default_install_kwargs)

    assert exc_info.value.exit_code == 1
