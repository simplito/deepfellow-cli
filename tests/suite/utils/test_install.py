# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.server.utils.workspace import Workspace
from deepfellow.suite.utils.install import install


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.create_admin")
@mock.patch("deepfellow.suite.utils.install.start_server")
@mock.patch("deepfellow.suite.utils.install.check_server_directory")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_model_install")
@mock.patch("deepfellow.suite.utils.install.infra_service_install")
@mock.patch("deepfellow.suite.utils.install.start_infra")
@mock.patch("deepfellow.suite.utils.install.check_infra_directory")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_success_calls_all_steps_in_order(
    mock_infra_install: Mock,
    mock_check_infra_directory: Mock,
    mock_start_infra: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_check_server_directory: Mock,
    mock_start_server: Mock,
    mock_create_admin: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install.call_count == 1
    assert mock_start_infra.call_count == 1
    assert mock_infra_service_install.call_count == 1
    assert mock_infra_service_install.call_args.kwargs["name"] == "ollama"
    assert mock_infra_model_install.call_count == 3
    assert mock_server_install.call_count == 1
    assert mock_server_install.call_args.kwargs["infra_api_key"] == "infra-api-key"
    assert mock_set_default_server_directory.call_count == 1
    assert mock_start_server.call_count == 1
    assert mock_create_admin.call_count == 1
    assert mock_create_admin.call_args.args[1:] == ("Admin", "admin@example.com", "Sup3r$ecret!")
    assert mock_get_token_from_login.call_count == 1
    assert mock_get_token_from_login.call_args.kwargs["email"] == "admin@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Sup3r$ecret!"
    assert mock_create_workspace.call_count == 1
    assert mock_create_workspace.call_args.args[2:] == ("Workspace", "Default", "app")


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_model_install")
@mock.patch("deepfellow.suite.utils.install.infra_service_install")
@mock.patch("deepfellow.suite.utils.install.start_infra")
@mock.patch("deepfellow.suite.utils.install.check_infra_directory")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_after_infra_install_error(
    mock_infra_install: Mock,
    mock_check_infra_directory: Mock,
    mock_start_infra: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_install.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_start_infra.call_count == 0
    assert mock_infra_service_install.call_count == 0
    assert mock_infra_model_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_model_install")
@mock.patch("deepfellow.suite.utils.install.infra_service_install")
@mock.patch("deepfellow.suite.utils.install.start_infra")
@mock.patch("deepfellow.suite.utils.install.check_infra_directory")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_after_model_install_failure_does_not_call_server_install(
    mock_infra_install: Mock,
    mock_check_infra_directory: Mock,
    mock_start_infra: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_model_install.side_effect = [None, typer.Exit(1), None]

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_model_install.call_count == 2
    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_model_install")
@mock.patch("deepfellow.suite.utils.install.infra_service_install")
@mock.patch("deepfellow.suite.utils.install.start_infra")
@mock.patch("deepfellow.suite.utils.install.check_infra_directory")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_when_infra_api_key_missing_does_not_call_server_install(
    mock_infra_install: Mock,
    mock_check_infra_directory: Mock,
    mock_start_infra: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = None

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_non_interactive_missing_credentials_fails(mock_echo: Mock) -> None:
    mock_echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_echo.prompt_until_valid.call_count == 1


@mock.patch("deepfellow.common.exceptions.echo")
@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_translates_bad_parameter_to_install_error(mock_echo: Mock, mock_exceptions_echo: Mock) -> None:
    """A caller outside Click (e.g. the suite Typer command) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter - mirroring how
    server's install() is made safe by the same @translate_to_install_error decorator."""
    mock_echo.prompt_until_valid.side_effect = typer.BadParameter("Invalid admin email")

    with pytest.raises(InstallError, match="Invalid admin email"):
        install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_exceptions_echo.error.call_args == mock.call("Invalid admin email")


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_translates_step_exit_to_install_error(mock_infra_install: Mock, mock_echo: Mock) -> None:
    """A step's typer.Exit (already normalized and re-raised by _run_step) must surface from
    install() as InstallError, not an unhandled typer.Exit - the same @translate_to_install_error
    contract as server's install()."""
    mock_infra_install.side_effect = typer.Exit(1)

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.create_admin")
@mock.patch("deepfellow.suite.utils.install.start_server")
@mock.patch("deepfellow.suite.utils.install.check_server_directory")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_model_install")
@mock.patch("deepfellow.suite.utils.install.infra_service_install")
@mock.patch("deepfellow.suite.utils.install.start_infra")
@mock.patch("deepfellow.suite.utils.install.check_infra_directory")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_prompted_credentials_are_reused_for_create_admin_and_login(
    mock_infra_install: Mock,
    mock_check_infra_directory: Mock,
    mock_start_infra: Mock,
    mock_infra_service_install: Mock,
    mock_infra_model_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_check_server_directory: Mock,
    mock_start_server: Mock,
    mock_create_admin: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_echo.prompt_until_valid.side_effect = ["Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!"]
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_create_admin.call_args.args[1:] == ("Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!")
    assert mock_get_token_from_login.call_args.kwargs["email"] == "prompted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pr0mpted$ecret!"
