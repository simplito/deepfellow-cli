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

import httpx
import pytest
import typer

from deepfellow.infra.mcp.install import install as install_command
from deepfellow.infra.utils.mcp import install


@pytest.fixture(name="name")
def name_fixture() -> str:
    return "brave-search"


def _model(model_id: str, spec_fields: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {"id": model_id, "type": "mcp", "installed": False, "custom": None, "spec": {"fields": spec_fields or []}}


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.fields.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_prompts_for_required_field_from_model_spec(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_install_with_progress: Mock,
    mock_fields_echo: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "list": [
            _model(
                "brave-search",
                [
                    {
                        "name": "envs",
                        "type": "map",
                        "required": False,
                        "description": "Custom environmental variables.\nRequired variables: BRAVE_API_KEY",
                        "default": '{"BRAVE_API_KEY": ""}',
                    }
                ],
            )
        ]
    }
    mock_fields_echo.prompt.return_value = '{"BRAVE_API_KEY": "sk-test-123"}'
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="brave-search", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"envs": '{"BRAVE_API_KEY": "sk-test-123"}'}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_not_found_reports_error_without_calling_install(
    mock_resolve: Mock, mock_make_request: Mock, mock_install_with_progress: Mock, mock_echo: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": [_model("brave-search")]}

    with pytest.raises(typer.Exit):
        install(name="unknown-server", spec=None)

    assert mock_install_with_progress.call_count == 0
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("MCP server 'unknown-server' not found.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_with_explicit_spec_skips_field_fetch(
    mock_resolve: Mock, mock_install_with_progress: Mock, mock_echo: Mock, mock_env_set: Mock
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="duckduckgo-test", spec='{"prefix": "duckduckgo-test"}')

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"prefix": "duckduckgo-test"}}
    assert mock_echo.success.call_count == 1


def test_install_raises_when_spec_is_blank(name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec="   ")


def test_install_raises_when_spec_and_set_args_given_together(name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec='{"a": "b"}', set_args=["a=b"])


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_exits_with_details_on_finish_status_error(
    mock_resolve: Mock, mock_make_request: Mock, mock_install_with_progress: Mock, mock_echo: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": [_model("brave-search")]}
    mock_install_with_progress.return_value = {
        "type": "finish",
        "status": "error",
        "details": "missing required environment variables: BRAVE_API_KEY",
    }

    with pytest.raises(typer.Exit):
        install(name="brave-search", spec=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Unable to install MCP server. missing required environment variables: BRAVE_API_KEY"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_skips_when_already_installed(
    mock_resolve: Mock, mock_make_request: Mock, mock_install_with_progress: Mock, mock_echo: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": [_model("brave-search")]}
    response = Mock(json=Mock(return_value={"error": {"message": "MCP server brave-search already installed"}}))
    mock_install_with_progress.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    install(name="brave-search", spec=None)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("MCP server 'brave-search' is already installed; skipping.")
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_install_points_to_infra_logs_when_finish_status_error_without_details(
    mock_resolve: Mock, mock_make_request: Mock, mock_install_with_progress: Mock, mock_echo: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": [_model("brave-search")]}
    mock_install_with_progress.return_value = {"type": "finish", "status": "error"}

    with pytest.raises(typer.Exit):
        install(name="brave-search", spec=None)

    assert mock_echo.error.call_count == 2
    assert mock_echo.error.call_args_list == [
        mock.call("Unable to install MCP server."),
        mock.call("Check `docker compose logs infra` for details."),
    ]
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.echo")
@mock.patch("deepfellow.infra.utils.fields.echo")
@mock.patch("deepfellow.infra.utils.mcp.install_with_progress")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch(
    "deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "connection-token")
)
def test_install_resolves_api_key_field_from_api_key_argument_not_connection_token(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_install_with_progress: Mock,
    mock_fields_echo: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "list": [
            _model(
                "brave-search",
                [{"name": "api_key", "type": "password", "required": True, "description": "API key"}],
            )
        ]
    }
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="brave-search", api_key="explicit-api-key", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "explicit-api-key"}}
    assert mock_fields_echo.prompt.call_count == 0
    assert mock_fields_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.infra.mcp.install.install_util")
def test_install_command_delegates_to_install_util(mock_install_util: Mock, name: str) -> None:
    install_command(name=name, server="http://infra:8086", api_key=None, spec=None, set_args=None, prompt_all=True)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(
        name=name, server="http://infra:8086", api_key=None, spec=None, set_args=None, prompt_all=True
    )
