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

from deepfellow.common.defaults import (
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_MONGO_PORT,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
)
from deepfellow.common.exceptions import InstallError
from deepfellow.common.state import state
from deepfellow.server.utils.workspace import Workspace
from deepfellow.suite.utils.install import install

_DEFAULT_INFRA_INSTALL_CALL = mock.call(
    template="workspace",
    force_install=False,
    port=DF_INFRA_PORT,
    image=DF_INFRA_IMAGE,
    local_image=False,
    directory=DF_INFRA_DIRECTORY,
    docker_config=None,
    storage=DF_INFRA_STORAGE_DIR,
    docker_network=DF_INFRA_DOCKER_NETWORK,
    explicitly_provided=set(),
)


def _default_server_install_call(*, force_install: bool = False) -> mock._Call:
    return mock.call(
        template="workspace",
        infra_api_key="infra-api-key",
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        force_install=force_install,
        port=DF_SERVER_PORT,
        image=DF_SERVER_IMAGE,
        local_image=False,
        directory=DF_SERVER_DIRECTORY,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        mongodb_port=DF_MONGO_PORT,
        mongodb_username="",
        mongodb_password="",
        falkordb_active=False,
        falkordb_url=DF_FALKORDB_URL,
        falkordb_username="",
        falkordb_password="",
        otel_local=False,
        explicitly_provided={"infra_api_key"},
    )


def _env_get_side_effect(*, infra_api_key: str | None = "infra-api-key", server_port: str | None = None):
    """A `env_get` side_effect distinguishing the DF_INFRA_API_KEY and DF_SERVER_PORT lookups.

    `install()` reads both from the freshly-installed .env files - a single shared
    `mock_env_get.return_value` can no longer serve both call sites now that server_url is built
    from the actually-resolved DF_SERVER_PORT rather than the raw CLI port."""
    values = {"DF_INFRA_API_KEY": infra_api_key}
    if server_port is not None:
        values["DF_SERVER_PORT"] = server_port

    def _side_effect(_path: Path, key: str, default: str | None = None) -> str | None:
        return values.get(key, default)

    return _side_effect


@mock.patch("deepfellow.suite.utils.install.assert_docker")
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
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.side_effect = _env_get_side_effect(server_port=str(DF_SERVER_PORT))
    mock_get_token_from_login.return_value = "token"
    workspace = Workspace(organization=Mock(), project=Mock(), api_key=Mock())
    mock_create_workspace.return_value = workspace

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_assert_docker.call_count == 1
    assert mock_infra_install.call_count == 1
    assert mock_infra_install.call_args == _DEFAULT_INFRA_INSTALL_CALL
    assert mock_env_get.call_count == 2
    assert mock_env_get.call_args_list[0].args == (DF_INFRA_DIRECTORY / ".env", "DF_INFRA_API_KEY")
    assert mock_env_get.call_args_list[1].args == (DF_SERVER_DIRECTORY / ".env", "DF_SERVER_PORT")
    assert mock_server_install.call_count == 1
    assert mock_server_install.call_args == _default_server_install_call()
    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call(DF_SERVER_DIRECTORY, force=False)
    assert mock_get_token_from_login.call_count == 1
    assert mock_get_token_from_login.call_args.args[1] == f"http://localhost:{DF_SERVER_PORT}"
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


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_force_install_to_infra_and_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", force_install=True)

    assert mock_infra_install.call_args == mock.call(**{**_DEFAULT_INFRA_INSTALL_CALL.kwargs, "force_install": True})
    assert mock_server_install.call_args == _default_server_install_call(force_install=True)


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_after_infra_install_error(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_infra_install.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_env_get.call_count == 0
    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_when_infra_api_key_missing_does_not_call_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = None

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
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
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_server_install.side_effect = InstallError("boom")

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_set_default_server_directory.call_count == 0
    assert mock_get_token_from_login.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_prompt_failure_is_translated_to_install_error(mock_echo: Mock, mock_assert_docker: Mock) -> None:
    mock_echo.prompt_until_valid.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name=None, admin_email=None, admin_password=None)

    assert mock_echo.prompt_until_valid.call_count == 1


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_non_interactive_reports_all_missing_admin_values(
    mock_infra_install: Mock, mock_echo: Mock, mock_assert_docker: Mock
) -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        install(admin_name=None, admin_email=None, admin_password=None)

    assert str(exc_info.value) == (
        "suite install is missing name, email, password; --non-interactive has no prompt to fall "
        "back on. Pass --admin-name/--admin-email/--admin-password"
    )
    assert mock_infra_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_non_interactive_reports_only_missing_admin_values(
    mock_infra_install: Mock, mock_echo: Mock, mock_assert_docker: Mock
) -> None:
    state.non_interactive = True

    with pytest.raises(InstallError) as exc_info:
        install(admin_name="Admin", admin_email=None, admin_password=None)

    assert str(exc_info.value) == (
        "suite install is missing email, password; --non-interactive has no prompt to fall back on. "
        "Pass --admin-name/--admin-email/--admin-password"
    )
    assert mock_infra_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
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
    mock_assert_docker: Mock,
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


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
def test_install_translates_bad_parameter_to_install_error(mock_echo: Mock, mock_assert_docker: Mock) -> None:
    """A caller outside Click (e.g. the suite Typer command) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter - mirroring how
    server's install() is made safe by the same @translate_to_install_error decorator."""
    mock_echo.prompt_until_valid.side_effect = typer.BadParameter("Invalid admin email")

    with pytest.raises(InstallError, match="Invalid admin email"):
        install(admin_name=None, admin_email=None, admin_password=None)


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_translates_step_exit_to_install_error(
    mock_infra_install: Mock, mock_echo: Mock, mock_assert_docker: Mock
) -> None:
    """A step's typer.Exit (already normalized and re-raised by _run_step) must surface from
    install() as InstallError, not an unhandled typer.Exit - the same @translate_to_install_error
    contract as server's install()."""
    mock_infra_install.side_effect = typer.Exit(1)

    with pytest.raises(InstallError, match="Installation failed"):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")


@mock.patch("deepfellow.suite.utils.install.assert_docker")
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
    mock_assert_docker: Mock,
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


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_checks_docker_before_prompting(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
) -> None:
    call_order: list[str] = []

    def _record_prompt(*args: object, **kwargs: object) -> str:
        call_order.append("prompt")
        return "value"

    mock_assert_docker.side_effect = lambda: call_order.append("assert_docker")
    mock_echo.prompt_until_valid.side_effect = _record_prompt
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name=None, admin_email=None, admin_password=None)

    assert call_order[0] == "assert_docker"
    assert mock_assert_docker.call_count == 1
    assert mock_infra_install.call_count == 1


@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_stops_when_docker_check_fails(
    mock_infra_install: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
) -> None:
    mock_assert_docker.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_infra_install.call_count == 0


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_distinct_infra_and_server_ports_independently(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.side_effect = _env_get_side_effect(server_port="9001")
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        infra_port=9000,
        server_port=9001,
    )

    assert mock_infra_install.call_args.kwargs["port"] == 9000
    assert mock_server_install.call_args.kwargs["port"] == 9001
    # server_url used for login/workspace-creation must follow the actually-installed server port.
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9001"


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_uses_resolved_server_port_over_cli_value_for_login_url(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    """If server_install() resolves a different port than the raw CLI value - e.g. restored from a
    prior install's own .env because --server-port wasn't passed this time - server_url must follow
    the actually-resolved port, not the value install() was called with, or login/workspace-creation
    would target a server that isn't listening there."""
    mock_env_get.side_effect = _env_get_side_effect(server_port="9002")
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install.call_args.kwargs["port"] == DF_SERVER_PORT
    assert mock_get_token_from_login.call_args.args[1] == "http://localhost:9002"


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_docker_network_to_both_infra_and_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        docker_network="my-custom-net",
    )

    assert mock_infra_install.call_args.kwargs["docker_network"] == "my-custom-net"
    assert mock_server_install.call_args.kwargs["docker_network"] == "my-custom-net"


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_falkordb_options_to_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        falkordb_active=True,
        falkordb_url="my-falkordb:6379",
        falkordb_username="graphuser",
        falkordb_password="graphpass",
    )

    assert mock_server_install.call_args.kwargs["falkordb_active"] is True
    assert mock_server_install.call_args.kwargs["falkordb_url"] == "my-falkordb:6379"
    assert mock_server_install.call_args.kwargs["falkordb_username"] == "graphuser"
    assert mock_server_install.call_args.kwargs["falkordb_password"] == "graphpass"


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_falkordb_disabled_by_default(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert mock_server_install.call_args.kwargs["falkordb_active"] is False


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_mongodb_port_and_credentials_to_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        mongodb_port=27018,
        mongodb_username="dfuser",
        mongodb_password="dfpass",
    )

    assert mock_server_install.call_args.kwargs["mongodb_port"] == 27018
    assert mock_server_install.call_args.kwargs["mongodb_username"] == "dfuser"
    assert mock_server_install.call_args.kwargs["mongodb_password"] == "dfpass"


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_otel_local_to_server_install(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!", otel_local=True)

    assert mock_server_install.call_args.kwargs["otel_local"] is True


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_reads_infra_api_key_from_custom_infra_directory(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    """A custom --infra-directory must be reflected in where the freshly-installed infra's own
    DF_INFRA_API_KEY is read back from - not the fixed DF_INFRA_DIRECTORY default."""
    custom_infra_directory = Path("/custom/infra")
    mock_env_get.side_effect = _env_get_side_effect(server_port=str(DF_SERVER_PORT))
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        infra_directory=custom_infra_directory,
    )

    assert mock_infra_install.call_args.kwargs["directory"] == custom_infra_directory
    assert mock_env_get.call_args_list[0].args == (custom_infra_directory / ".env", "DF_INFRA_API_KEY")


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_forwards_custom_server_directory_to_set_default_server_directory(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    custom_server_directory = Path("/custom/server")
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        server_directory=custom_server_directory,
    )

    assert mock_server_install.call_args.kwargs["directory"] == custom_server_directory
    assert mock_set_default_server_directory.call_args == mock.call(custom_server_directory, force=False)


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_maps_explicitly_provided_to_infra_and_server_port_only(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    """explicitly_provided={"infra_port"} must reach only infra_install()'s own "port" key, not
    server_install()'s - the two ports are independent despite sharing the same target field name."""
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        explicitly_provided={"infra_port"},
    )

    assert mock_infra_install.call_args.kwargs["explicitly_provided"] == {"port"}
    assert mock_server_install.call_args.kwargs["explicitly_provided"] == {"infra_api_key"}


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_maps_explicitly_provided_docker_network_to_both(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    mock_env_get.return_value = "infra-api-key"
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(
        admin_name="Admin",
        admin_email="admin@example.com",
        admin_password="Sup3r$ecret!",
        explicitly_provided={"docker_network"},
    )

    assert mock_infra_install.call_args.kwargs["explicitly_provided"] == {"docker_network"}
    assert mock_server_install.call_args.kwargs["explicitly_provided"] == {"docker_network", "infra_api_key"}


@mock.patch("deepfellow.suite.utils.install.assert_docker")
@mock.patch("deepfellow.suite.utils.install.echo")
@mock.patch("deepfellow.suite.utils.install.env_get")
@mock.patch("deepfellow.suite.utils.install.update_project")
@mock.patch("deepfellow.suite.utils.install.create_workspace")
@mock.patch("deepfellow.suite.utils.install.get_token_from_login")
@mock.patch("deepfellow.suite.utils.install.set_default_server_directory")
@mock.patch("deepfellow.suite.utils.install.server_install")
@mock.patch("deepfellow.suite.utils.install.infra_install")
def test_install_always_marks_infra_api_key_as_explicitly_provided(
    mock_infra_install: Mock,
    mock_server_install: Mock,
    mock_set_default_server_directory: Mock,
    mock_get_token_from_login: Mock,
    mock_create_workspace: Mock,
    mock_update_project: Mock,
    mock_env_get: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
) -> None:
    """infra_api_key is always freshly read from the infra suite itself just installed, never a
    CLI flag - it must never be silently outranked by a future template's own "infra_api_key",
    unlike port/docker_network, whose explicit status genuinely depends on what the user passed."""
    mock_env_get.side_effect = _env_get_side_effect(server_port=str(DF_SERVER_PORT))
    mock_get_token_from_login.return_value = "token"
    mock_create_workspace.return_value = Workspace(organization=Mock(), project=Mock(), api_key=Mock())

    install(admin_name="Admin", admin_email="admin@example.com", admin_password="Sup3r$ecret!")

    assert "infra_api_key" in mock_server_install.call_args.kwargs["explicitly_provided"]
