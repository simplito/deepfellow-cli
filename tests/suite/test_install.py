# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the suite install command."""

from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.common.exceptions import InstallError
from deepfellow.suite.install import app
from deepfellow.suite.install import install as install_command

runner = CliRunner()


@pytest.fixture
def default_install_kwargs() -> dict:
    return {
        "admin_name": "Admin",
        "admin_email": "admin@example.com",
        "admin_password": "Sup3r$ecret!",
        "force_install": False,
    }


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_delegates_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(**default_install_kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**default_install_kwargs)


@mock.patch("deepfellow.common.validation.validate_email_lib")
@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_reads_admin_credentials_from_env_vars(
    mock_install_util: Mock,
    mock_validate_email_lib: Mock,
) -> None:
    """--admin-name/--admin-email/--admin-password must be settable via DF_SERVER_ADMIN_* env vars,
    same as server install, so scripted/non-interactive suite installs don't have to pass the
    password as a CLI argument."""
    mock_validate_email_lib.return_value = SimpleNamespace(email="admin@example.com")

    result = runner.invoke(
        app,
        [],
        env={
            "DF_SERVER_ADMIN_NAME": "Admin User",
            "DF_SERVER_ADMIN_EMAIL": "admin@example.com",
            "DF_SERVER_ADMIN_PASSWORD": "Password1!",
        },
    )

    assert result.exit_code == 0, result.output
    assert mock_install_util.call_args == mock.call(
        admin_name="Admin User", admin_email="admin@example.com", admin_password="Password1!", force_install=False
    )


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_translates_install_error_to_exit(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(**default_install_kwargs)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_forwards_force_install_flag(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(**{**default_install_kwargs, "force_install": True})

    assert mock_install_util.call_args == mock.call(**{**default_install_kwargs, "force_install": True})
