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

from deepfellow.common.state import state
from deepfellow.infra.mcp.list import list as list_command
from deepfellow.infra.utils.mcp import McpServer, _list, list_servers


def _model(
    model_id: str,
    custom_model_id: str | None,
    installed: bool = True,
    custom_spec: dict[str, object] | None = None,
    spec: dict[str, object] | None = None,
    description: str | None = None,
) -> dict[str, object]:
    return {
        "id": model_id,
        "type": "mcp",
        "installed": installed,
        "custom": custom_model_id,
        "custom_spec": custom_spec,
        "spec": spec,
        "description": description,
    }


def test_str_omits_custom_model_id_by_default() -> None:
    server = McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1")

    result = str(server)

    assert "id: my-server" in result.splitlines()
    assert "kind: mcp" in result.splitlines()
    assert "installed: True" in result.splitlines()
    assert "custom_model_id" not in result


def test_str_includes_custom_model_id_in_debug_mode() -> None:
    server = McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1")
    state.debug = True

    try:
        result = str(server)
    finally:
        state.reset()

    assert "custom_model_id: cm-1" in result.splitlines()


def test_str_shows_installed_true_and_parameters_when_custom_spec_is_present() -> None:
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed=True,
        custom_model_id="cm-1",
        custom_spec={"command": "npx", "args": ["my-mcp"]},
    )

    result = str(server)

    assert "installed: True" in result.splitlines()
    assert "parameters:" in result.splitlines()
    assert "  command: npx" in result.splitlines()
    assert "  args: ['my-mcp']" in result.splitlines()


def test_str_shows_installed_false_and_no_parameters_for_an_uninstalled_custom_model() -> None:
    # Regression test: a not-yet-installed model's `installed` boolean must be shown as-is, not
    # inferred from whether the entry happens to carry a `custom_spec`/install-form `spec`.
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed=False,
        custom_model_id="cm-1",
        custom_spec=None,
    )

    result = str(server)

    assert "installed: False" in result.splitlines()
    assert "parameters:" not in result.splitlines()


def test_str_falls_back_to_installed_dict_when_custom_spec_is_absent() -> None:
    # Some other df-cli list endpoints report a dict of runtime config directly under
    # `installed` (see `deepfellow.infra.utils.connection.is_installed`) - `installed: True` is
    # still shown in that case, even though the CLI only ever reads `custom_spec` for `parameters:`.
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed={"command": "npx", "args": ["my-mcp"]},
        custom_model_id="cm-1",
    )

    result = str(server)

    assert "installed: True" in result.splitlines()
    assert "parameters:" not in result.splitlines()


def test_str_shows_description_when_present() -> None:
    server = McpServer(
        id="brave-search",
        kind="mcp",
        installed=False,
        custom_model_id=None,
        description="Web search via the Brave Search API.",
    )

    result = str(server)

    assert "description: Web search via the Brave Search API." in result.splitlines()


def test_str_omits_description_when_absent() -> None:
    server = McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1")

    result = str(server)

    assert "description" not in result


def test_str_shows_fields_when_not_installed() -> None:
    server = McpServer(
        id="brave-search",
        kind="mcp",
        installed=False,
        custom_model_id=None,
        fields=[
            {
                "name": "envs",
                "type": "map",
                # Schema-optional, but its description still names a required sub-value - this
                # must still show up, since the `required` flag alone doesn't capture that.
                "required": False,
                "description": "Required variables: BRAVE_API_KEY",
                "default": '{"BRAVE_API_KEY": ""}',
            },
            {"name": "prefix", "type": "text", "required": True, "description": "Endpoint prefix", "default": None},
        ],
    )

    result = str(server)

    assert "fields:" in result.splitlines()
    lines = result.splitlines()
    assert any(line.startswith("  - envs:") and "BRAVE_API_KEY" in line for line in lines)
    assert any(line.startswith("  - prefix:") for line in lines)


def test_str_omits_fields_once_installed() -> None:
    # Once installed, the install-form fields no longer describe anything actionable - a custom
    # model's `parameters:` (from custom_spec) already shows its real configuration instead.
    server = McpServer(
        id="brave-search",
        kind="mcp",
        installed=True,
        custom_model_id=None,
        fields=[{"name": "envs", "type": "map", "required": True, "description": "...", "default": None}],
    )

    result = str(server)

    assert "fields:" not in result.splitlines()


def test_str_redacts_credential_bearing_fields_in_custom_spec() -> None:
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed=True,
        custom_model_id="cm-1",
        custom_spec={"envs": {"GITHUB_TOKEN": "secret-token"}, "kind": "user"},
    )

    result = str(server)

    assert "secret-token" not in result
    assert "  envs: {'GITHUB_TOKEN': '*****'}" in result.splitlines()
    assert "  kind: user" in result.splitlines()


def test_str_redacts_credential_bearing_fields_nested_under_another_key() -> None:
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed=True,
        custom_model_id="cm-1",
        custom_spec={"nested": {"envs": {"GITHUB_TOKEN": "secret-token"}}},
    )

    result = str(server)

    assert "secret-token" not in result
    assert "  nested: {'envs': {'GITHUB_TOKEN': '*****'}}" in result.splitlines()


def test_str_redacts_credential_bearing_fields_nested_in_a_list_of_dicts() -> None:
    server = McpServer(
        id="my-server",
        kind="mcp",
        installed=True,
        custom_model_id="cm-1",
        custom_spec={"tools": [{"envs": {"GITHUB_TOKEN": "secret-token"}}]},
    )

    result = str(server)

    assert "secret-token" not in result
    assert "  tools: [{'envs': {'GITHUB_TOKEN': '*****'}}]" in result.splitlines()


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_returns_mcp_server_list(mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock) -> None:
    mock_make_request.return_value = {"list": [_model("my-server", "cm-1")]}

    result = list_servers(server=None)

    assert result == [McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1", custom_spec=None)]
    assert mock_make_request.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/mcp/models",
        token="test-key",
        err_msg="Unable to list MCP servers.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_reads_custom_spec_field_from_the_response(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": [_model("my-server", "cm-1", custom_spec={"command": "npx"})]}

    result = list_servers(server=None)

    assert result == [
        McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1", custom_spec={"command": "npx"})
    ]


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_reads_description_and_fields_from_the_response(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    fields = [{"name": "envs", "type": "map", "required": True, "description": "...", "default": None}]
    mock_make_request.return_value = {
        "list": [_model("brave-search", None, installed=False, spec={"fields": fields}, description="Web search.")]
    }

    result = list_servers(server=None)

    assert result == [
        McpServer(
            id="brave-search",
            kind="mcp",
            installed=False,
            custom_model_id=None,
            description="Web search.",
            fields=fields,
        )
    ]


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_does_not_reannounce_connection_persistence(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    # Regression test: a read-only `mcp list` shouldn't print "Updated config/secrets" every
    # time it's run against an already-known, already-working connection.
    mock_make_request.return_value = {"list": []}

    list_servers(server=None)

    assert mock_env_set.call_count == 2
    assert all(call.kwargs.get("quiet") is True for call in mock_env_set.call_args_list)


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_returns_empty_list_when_no_servers_provisioned(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": []}

    result = list_servers(server=None)

    assert result == []


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_list_forwards_quiet_to_call_infra(mock_make_request: Mock, mock_env_set: Mock) -> None:
    mock_make_request.return_value = {"list": []}

    _list("http://infra:8086", "test-key", quiet=True)

    assert mock_env_set.call_count == 2
    assert all(call.kwargs.get("quiet") is True for call in mock_env_set.call_args_list)


@mock.patch("deepfellow.infra.utils.models.echo.error")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_exits_when_list_field_is_missing(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {"unexpected": "shape"}

    with pytest.raises(typer.Exit):
        list_servers(server=None)

    assert mock_error.call_count == 1


@mock.patch("deepfellow.infra.utils.models.echo.error")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_servers_exits_when_list_item_is_not_a_dict(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {"list": ["not-a-dict"]}

    with pytest.raises(typer.Exit):
        list_servers(server=None)

    assert mock_error.call_count == 1


@mock.patch("deepfellow.infra.mcp.list.echo.info")
@mock.patch("deepfellow.infra.mcp.list.list_servers")
def test_list_command_prints_provisioned_servers(mock_list_servers: Mock, mock_info: Mock) -> None:
    server = McpServer(id="my-server", kind="mcp", installed=True, custom_model_id="cm-1")
    mock_list_servers.return_value = [server]

    list_command(server="http://infra:8086")

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(server))


@mock.patch("deepfellow.infra.mcp.list.echo.info")
@mock.patch("deepfellow.infra.mcp.list.list_servers")
def test_list_command_prints_info_message_when_empty(mock_list_servers: Mock, mock_info: Mock) -> None:
    mock_list_servers.return_value = []

    list_command(server="http://infra:8086")

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("No MCP servers provisioned.")
