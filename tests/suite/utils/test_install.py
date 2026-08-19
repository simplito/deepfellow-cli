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
from deepfellow.common.state import state
from deepfellow.server.utils.workspace import Workspace
from deepfellow.suite.utils.install import install


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_success_calls_all_steps_in_order(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    workspace = Workspace(organization=Mock(), project=Mock(), api_key=Mock())
    mock_create_workspace.return_value = workspace

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install.call_count == 1
    assert mock_infra_install.call_args == mock.call(template="workspace")
    assert mock_env_get.call_count == 1
    assert mock_env_get.call_args.args[1] == "DF_INFRA_API_KEY"
    assert mock_server_install.call_count == 1
    assert mock_server_install.call_args == mock.call(
        template="workspace",
        infra_api_key="infra-api-key",
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
    )
    assert mock_set_default_server_directory.call_count == 1
    assert mock_get_token_from_login.call_count == 1
    assert mock_get_token_from_login.call_args.kwargs["email"] == "admin@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Sup3r$ecret!"
    assert mock_create_workspace.call_count == 1
    assert mock_create_workspace.call_args.args[2:] == ("Workspace", "Default", "app")
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args.args[2:] == (
        workspace.organization.id,
        workspace.project.id,
        {"models": ["gemma4:e4b", "mxbai-embed-large", "qwen3.5:4b"]},
    )


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_after_infra_install_error(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_infra_install.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_env_get.call_count == 0
    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_when_infra_api_key_missing_does_not_call_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = None

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_after_server_install_error_does_not_call_login(
    mock_infra_install: Mock,
    mock_env_get: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_server_install.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_set_default_server_directory.call_count == 0
    assert mock_get_token_from_login.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_prompt_failure_is_translated_to_install_error(mock_echo: Mock) -> None:
    mock_echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_echo.prompt_until_valid.call_count == 1


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_non_interactive_reports_all_missing_admin_values(mock_infra_install: Mock, mock_echo: Mock) -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        install(admin_name=None, admin_email=None, admin_password=None)

    assert str(exc_info.value) == (
        "suite install is missing name, email, password; --non-interactive has no prompt to fall "
        "back on. Pass --admin-name/--admin-email/--admin-password"
    )
    assert mock_infra_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_non_interactive_reports_only_missing_admin_values(mock_infra_install: Mock, mock_echo: Mock) -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        install(admin_name="Admin", admin_email=None, admin_password=None)

    assert str(exc_info.value) == (
        "suite install is missing email, password; --non-interactive has no prompt to fall back on. "
        "Pass --admin-name/--admin-email/--admin-password"
    )
    assert mock_infra_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_non_interactive_with_all_admin_values_proceeds(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    state.non_interactive = True
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_infra_install.call_count == 1
    assert mock_server_install.call_count == 1
    assert mock_set_default_server_directory.call_count == 1
    assert mock_update_project.call_count == 1
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_translates_bad_parameter_to_install_error(mock_echo: Mock) -> None:
    """A caller outside Click (e.g. the suite Typer command) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter - mirroring how
    server's install() is made safe by the same @translate_to_install_error decorator."""
    mock_echo.prompt_until_valid.side_effect = typer.BadParameter("Invalid admin email")

    with pytest.raises(InstallError, match="Invalid admin email"):
        install(admin_name=None, admin_email=None, admin_password=None)


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
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_prompted_credentials_are_reused_for_server_install_and_login(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_echo.prompt_until_valid.side_effect = ["Prompted Admin", "prompted@example.com", "Pr0mpted$ecret!"]
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_server_install.call_args.kwargs["admin_name"] == "Prompted Admin"
    assert mock_server_install.call_args.kwargs["admin_email"] == "prompted@example.com"
    assert mock_server_install.call_args.kwargs["admin_password"] == "Pr0mpted$ecret!"
    assert mock_get_token_from_login.call_args.kwargs["email"] == "prompted@example.com"
    assert mock_get_token_from_login.call_args.kwargs["password"] == "Pr0mpted$ecret!"
