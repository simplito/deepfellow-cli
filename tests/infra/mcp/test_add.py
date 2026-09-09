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

from deepfellow.common.state import state
from deepfellow.infra.mcp.add import _CONFIG_EXAMPLE_HINT, _validate_config_path
from deepfellow.infra.mcp.add import add as add_command
from deepfellow.infra.utils.mcp import add, ensure_name_available


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_converts_config_and_provisions_custom_model(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_info: Mock
) -> None:
    mock_make_request.side_effect = [
        {"kind": "user", "name": "old-name", "command": "npx"},
        {"custom_model_id": "cm-1"},
    ]

    result = add(name="my-server", config={"mcpServers": {"old-name": {"command": "npx"}}}, server=None)

    assert result == "cm-1"
    assert mock_make_request.call_count == 2
    assert mock_make_request.call_args_list[0] == mock.call(
        method="POST",
        url="http://infra:8086/admin/mcp/convert-config",
        token="test-key",
        data={"config": {"mcpServers": {"old-name": {"command": "npx"}}}},
        err_msg="Unable to convert MCP config.",
        reraise=True,
    )
    assert mock_make_request.call_args_list[1] == mock.call(
        method="POST",
        url="http://infra:8086/admin/services/mcp/models/custom",
        token="test-key",
        data={"spec": {"kind": "user", "id": "my-server", "name": "my-server", "command": "npx"}},
        err_msg="Unable to add MCP server.",
        reraise=True,
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("Converted MCP server config:\nkind: user\nname: old-name\ncommand: npx")


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_ensure_name_available_exits_when_name_collides_with_builtin_model(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {"list": [{"id": "my-server", "type": "mcp", "installed": False, "custom": None}]}

    with pytest.raises(typer.Exit):
        ensure_name_available("my-server", server=None)

    assert mock_make_request.call_count == 1
    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call(
        "MCP server 'my-server' is a built-in model. Choose a different name for your custom server."
    )


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_ensure_name_available_exits_when_name_collides_with_custom_model(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {
        "list": [{"id": "my-server", "type": "mcp", "installed": False, "custom": "cm-1"}]
    }

    with pytest.raises(typer.Exit):
        ensure_name_available("my-server", server=None)

    assert mock_make_request.call_count == 1
    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call(
        "MCP server 'my-server' already exists. Choose a different name, or run `mcp uninstall my-server --purge` "
        "first."
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_ensure_name_available_returns_resolved_server_when_name_is_free(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock
) -> None:
    mock_make_request.return_value = {"list": []}

    result = ensure_name_available("my-server", server=None)

    assert result == "http://infra:8086"


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_redacts_credential_bearing_fields_when_printing_converted_spec(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_info: Mock
) -> None:
    mock_make_request.side_effect = [
        {
            "kind": "user",
            "name": "old-name",
            "envs": {"GITHUB_TOKEN": "secret-token"},
            "headers": {"Authorization": "Bearer secret"},
            "oauth": "secret-oauth-config",
        },
        {"custom_model_id": "cm-1"},
    ]

    add(name="my-server", config={"mcpServers": {"old-name": {"command": "npx"}}}, server=None)

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(
        "Converted MCP server config:\n"
        "kind: user\n"
        "name: old-name\n"
        "envs: {'GITHUB_TOKEN': '*****'}\n"
        "headers: {'Authorization': '*****'}\n"
        "oauth: *****"
    )
    assert mock_make_request.call_args_list[1] == mock.call(
        method="POST",
        url="http://infra:8086/admin/services/mcp/models/custom",
        token="test-key",
        data={
            "spec": {
                "kind": "user",
                "id": "my-server",
                "name": "my-server",
                "envs": {"GITHUB_TOKEN": "secret-token"},
                "headers": {"Authorization": "Bearer secret"},
                "oauth": "secret-oauth-config",
            }
        },
        err_msg="Unable to add MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_masks_embedded_secrets_in_non_allowlisted_fields(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_info: Mock
) -> None:
    mock_make_request.side_effect = [
        {
            "kind": "custom",
            "name": "iris",
            "command": "docker",
            "args": ["run", "-e", "GITHUB_TOKEN=ghp_secretvalue", "myimage:latest"],
            "server_url": "https://example.com/mcp?token=abc123",
            "timeout": 30,
        },
        {"custom_model_id": "cm-1"},
    ]

    add(
        name="my-server",
        config={"mcpServers": {"iris": {"command": "docker"}}},
        server=None,
        prefix="my-prefix",
        image_port=8000,
    )

    printed = mock_info.call_args_list[0].args[0]
    assert "ghp_secretvalue" not in printed
    assert "abc123" not in printed
    assert "GITHUB_TOKEN=*****" in printed
    assert "token=*****" in printed
    assert "timeout: 30" in printed
    # The unredacted spec is still what gets provisioned.
    assert mock_make_request.call_args_list[1] == mock.call(
        method="POST",
        url="http://infra:8086/admin/services/mcp/models/custom",
        token="test-key",
        data={
            "spec": {
                "kind": "custom",
                "id": "my-server",
                "name": "my-server",
                "command": "docker",
                "args": ["run", "-e", "GITHUB_TOKEN=ghp_secretvalue", "myimage:latest"],
                "server_url": "https://example.com/mcp?token=abc123",
                "timeout": 30,
                "default_prefix": "my-prefix",
                "image_port": 8000,
            }
        },
        err_msg="Unable to add MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_masks_bearer_header_and_args_flag_value_pair(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_info: Mock
) -> None:
    mock_make_request.side_effect = [
        {
            "kind": "custom",
            "name": "iris",
            "command": "npx",
            "args": ["--api-key", "sk-inline-secret", "--header", "Authorization: Bearer sk-supersecret123", 1],
        },
        {"custom_model_id": "cm-1"},
    ]

    add(
        name="my-server",
        config={"mcpServers": {"iris": {"command": "npx"}}},
        server=None,
        prefix="my-prefix",
        image_port=8000,
    )

    printed = mock_info.call_args_list[0].args[0]
    assert "sk-inline-secret" not in printed
    assert "sk-supersecret123" not in printed
    assert "*****" in printed


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_exits_when_converted_spec_is_not_a_json_object(
    mock_resolve: Mock, mock_make_request: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = ["not", "an", "object"]

    with pytest.raises(typer.Exit):
        add(name="my-server", config={"command": "npx"}, server=None)

    assert mock_error.call_count == 1
    assert mock_make_request.call_count == 1


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_asks_for_prefix_and_image_port_when_kind_is_custom(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_info: Mock
) -> None:
    mock_make_request.side_effect = [
        {"kind": "custom", "name": "iris", "image": "myimage:latest"},
        {"custom_model_id": "cm-1"},
    ]

    result = add(
        name="my-server",
        config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
        server=None,
        prefix="my-prefix",
        image_port=8000,
    )

    assert result == "cm-1"
    assert mock_make_request.call_args_list[1] == mock.call(
        method="POST",
        url="http://infra:8086/admin/services/mcp/models/custom",
        token="test-key",
        data={
            "spec": {
                "kind": "custom",
                "id": "my-server",
                "name": "my-server",
                "image": "myimage:latest",
                "default_prefix": "my-prefix",
                "image_port": 8000,
            }
        },
        err_msg="Unable to add MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_raises_bad_parameter_when_image_port_out_of_range_in_non_interactive_mode(
    mock_resolve: Mock, mock_make_request: Mock
) -> None:
    state.non_interactive = True
    mock_make_request.return_value = {"kind": "custom", "name": "iris", "image": "myimage:latest"}

    with pytest.raises(typer.BadParameter):
        add(
            name="my-server",
            config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
            server=None,
            prefix="my-prefix",
            image_port=99999,
        )

    assert mock_make_request.call_count == 1


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_exits_when_kind_is_custom_and_prefix_missing_in_non_interactive_mode(
    mock_resolve: Mock, mock_make_request: Mock, mock_error: Mock
) -> None:
    state.non_interactive = True
    mock_make_request.return_value = {"kind": "custom", "name": "iris", "image": "myimage:latest"}

    with pytest.raises(typer.Exit):
        add(
            name="my-server",
            config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
            server=None,
        )

    assert mock_make_request.call_count == 1


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_exits_when_stdin_not_tty_and_prefix_missing(
    mock_resolve: Mock, mock_make_request: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {"kind": "custom", "name": "iris", "image": "myimage:latest"}

    with pytest.raises(typer.Exit):
        add(
            name="my-server",
            config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
            server=None,
            stdin_is_tty=False,
        )

    assert mock_error.call_count == 1
    assert mock_error.call_args == mock.call(
        "This MCP config requires --prefix and --image-port when the config is piped on stdin."
    )
    assert mock_make_request.call_count == 1


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_exits_when_stdin_not_tty_and_image_port_missing(
    mock_resolve: Mock, mock_make_request: Mock, mock_error: Mock
) -> None:
    mock_make_request.return_value = {"kind": "custom", "name": "iris", "image": "myimage:latest"}

    with pytest.raises(typer.Exit):
        add(
            name="my-server",
            config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
            server=None,
            prefix="my-prefix",
            stdin_is_tty=False,
        )

    assert mock_error.call_count == 1
    assert mock_make_request.call_count == 1


@mock.patch("deepfellow.infra.utils.mcp.echo.info")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.echo.prompt")
@mock.patch("deepfellow.infra.utils.mcp.echo.prompt_until_valid")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_prompts_for_prefix_and_image_port_when_stdin_is_a_tty(
    mock_resolve: Mock,
    mock_prompt_until_valid: Mock,
    mock_prompt: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    mock_info: Mock,
) -> None:
    mock_make_request.side_effect = [
        {"kind": "custom", "name": "iris", "image": "myimage:latest"},
        {"custom_model_id": "cm-1"},
    ]
    mock_prompt.return_value = "my-prefix"
    mock_prompt_until_valid.return_value = 8000

    result = add(
        name="my-server",
        config={"mcpServers": {"iris": {"command": "docker", "args": ["run", "myimage:latest"]}}},
        server=None,
        stdin_is_tty=True,
    )

    assert result == "cm-1"
    assert mock_prompt.call_count == 1
    assert mock_prompt_until_valid.call_count == 1
    assert mock_make_request.call_args_list[1] == mock.call(
        method="POST",
        url="http://infra:8086/admin/services/mcp/models/custom",
        token="test-key",
        data={
            "spec": {
                "kind": "custom",
                "id": "my-server",
                "name": "my-server",
                "image": "myimage:latest",
                "default_prefix": "my-prefix",
                "image_port": 8000,
            }
        },
        err_msg="Unable to add MCP server.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.utils.mcp.echo.error")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.mcp.make_request")
@mock.patch("deepfellow.infra.utils.mcp.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_add_exits_when_response_missing_custom_model_id(
    mock_resolve: Mock, mock_make_request: Mock, mock_env_set: Mock, mock_error: Mock
) -> None:
    mock_make_request.side_effect = [
        {"kind": "user", "name": "old-name", "command": "npx"},
        {},
    ]

    with pytest.raises(typer.Exit):
        add(name="my-server", config={"mcpServers": {"old-name": {"command": "npx"}}}, server=None)

    assert mock_error.call_count == 1
    assert mock_make_request.call_count == 2


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_delegates_to_add_util(
    mock_stdin: Mock, mock_add_util: Mock, mock_ensure_name_available: Mock, tmp_path: Path
) -> None:
    mock_stdin.isatty.return_value = True
    mock_add_util.return_value = "cm-1"
    config_file = tmp_path / "config.json"
    config_file.write_text('{"command": "npx"}')

    add_command(name="my-server", server="http://infra:8086", config=config_file, prefix=None, image_port=None)

    assert mock_ensure_name_available.call_args == mock.call("my-server", "http://infra:8086")
    assert mock_add_util.call_count == 1
    assert mock_add_util.call_args == mock.call(
        name="my-server",
        config={"command": "npx"},
        server="http://infra:8086",
        prefix=None,
        image_port=None,
        stdin_is_tty=True,
    )


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.echo.debug")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_logs_custom_model_id_in_debug_mode(
    mock_stdin: Mock, mock_add_util: Mock, mock_debug: Mock, mock_ensure_name_available: Mock, tmp_path: Path
) -> None:
    mock_stdin.isatty.return_value = True
    mock_add_util.return_value = "cm-1"
    config_file = tmp_path / "config.json"
    config_file.write_text('{"command": "npx"}')
    state.debug = True

    try:
        add_command(name="my-server", server="http://infra:8086", config=config_file, prefix=None, image_port=None)
    finally:
        state.reset()

    assert mock_debug.call_args == mock.call("custom_model_id: cm-1")


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_reads_config_from_stdin_when_no_config_given(
    mock_stdin: Mock, mock_add_util: Mock, mock_ensure_name_available: Mock
) -> None:
    mock_stdin.isatty.return_value = False
    mock_stdin.read.return_value = '{"command": "npx"}'
    mock_add_util.return_value = "cm-1"

    add_command(name="my-server", server="http://infra:8086", config=None, prefix=None, image_port=None)

    assert mock_add_util.call_count == 1
    assert mock_add_util.call_args == mock.call(
        name="my-server",
        config={"command": "npx"},
        server="http://infra:8086",
        prefix=None,
        image_port=None,
        stdin_is_tty=False,
    )


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_passes_stdin_is_tty_false_when_config_is_a_file_but_stdin_is_redirected(
    mock_stdin: Mock, mock_add_util: Mock, mock_ensure_name_available: Mock, tmp_path: Path
) -> None:
    """--config from a file doesn't guarantee stdin is promptable (e.g. CI with stdin closed)."""
    mock_stdin.isatty.return_value = False
    mock_add_util.return_value = "cm-1"
    config_file = tmp_path / "config.json"
    config_file.write_text('{"command": "npx"}')

    add_command(name="my-server", server="http://infra:8086", config=config_file, prefix=None, image_port=None)

    assert mock_add_util.call_count == 1
    assert mock_add_util.call_args == mock.call(
        name="my-server",
        config={"command": "npx"},
        server="http://infra:8086",
        prefix=None,
        image_port=None,
        stdin_is_tty=False,
    )
    assert mock_stdin.read.call_count == 0


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.echo.error")
def test_add_command_exits_when_config_file_read_fails(
    mock_error: Mock, mock_ensure_name_available: Mock, tmp_path: Path
) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_bytes(b"\xff\xfe\x00\x01")

    with pytest.raises(typer.Exit):
        add_command(name="my-server", server="http://infra:8086", config=config_file)

    assert mock_error.call_count == 1


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
def test_add_command_exits_when_config_is_invalid_json(mock_ensure_name_available: Mock, tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text("not json")

    with pytest.raises(typer.Exit):
        add_command(name="my-server", server="http://infra:8086", config=config_file)


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
def test_add_command_exits_when_config_is_not_a_json_object(mock_ensure_name_available: Mock, tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text('["not", "an", "object"]')

    with pytest.raises(typer.Exit):
        add_command(name="my-server", server="http://infra:8086", config=config_file)


def test_validate_config_path_returns_path_when_file_exists(tmp_path: Path) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text("{}")

    result = _validate_config_path(str(config_file))

    assert result == config_file


def test_validate_config_path_raises_bad_parameter_when_file_missing(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.json"

    with pytest.raises(typer.BadParameter, match="File not found"):
        _validate_config_path(str(missing_file))


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.echo.prompt_until_valid")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_prompts_for_config_path_when_no_config_and_stdin_is_a_tty(
    mock_stdin: Mock,
    mock_prompt_until_valid: Mock,
    mock_add_util: Mock,
    mock_ensure_name_available: Mock,
    tmp_path: Path,
) -> None:
    mock_stdin.isatty.return_value = True
    config_file = tmp_path / "config.json"
    config_file.write_text('{"command": "npx"}')
    mock_prompt_until_valid.return_value = config_file
    mock_add_util.return_value = "cm-1"

    add_command(name="my-server", server="http://infra:8086", config=None, prefix=None, image_port=None)

    assert mock_prompt_until_valid.call_count == 1
    assert mock_add_util.call_count == 1
    assert mock_add_util.call_args == mock.call(
        name="my-server",
        config={"command": "npx"},
        server="http://infra:8086",
        prefix=None,
        image_port=None,
        stdin_is_tty=True,
    )


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.add_util")
@mock.patch("deepfellow.infra.mcp.add.echo.prompt_until_valid")
@mock.patch("deepfellow.infra.mcp.add.echo.info")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_shows_config_example_before_prompting_for_config_path(
    mock_stdin: Mock,
    mock_info: Mock,
    mock_prompt_until_valid: Mock,
    mock_add_util: Mock,
    mock_ensure_name_available: Mock,
    tmp_path: Path,
) -> None:
    mock_stdin.isatty.return_value = True
    config_file = tmp_path / "config.json"
    config_file.write_text('{"command": "npx"}')
    mock_prompt_until_valid.return_value = config_file
    mock_add_util.return_value = "cm-1"

    add_command(name="my-server", server="http://infra:8086", config=None, prefix=None, image_port=None)

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(_CONFIG_EXAMPLE_HINT)


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available", return_value="http://infra:8086")
@mock.patch("deepfellow.infra.mcp.add.echo.error")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_exits_when_config_and_stdin_are_both_empty(
    mock_stdin: Mock, mock_error: Mock, mock_ensure_name_available: Mock
) -> None:
    mock_stdin.isatty.return_value = False
    mock_stdin.read.return_value = "  "

    with pytest.raises(typer.Exit):
        add_command(name="my-server", server="http://infra:8086", config=None)

    assert mock_error.call_count == 1


@mock.patch("deepfellow.infra.mcp.add.ensure_name_available")
@mock.patch("deepfellow.infra.mcp.add.echo.prompt_until_valid")
@mock.patch("deepfellow.infra.mcp.add.echo.info")
@mock.patch("deepfellow.infra.mcp.add.sys.stdin")
def test_add_command_checks_name_availability_before_prompting_for_config_path(
    mock_stdin: Mock, mock_info: Mock, mock_prompt_until_valid: Mock, mock_ensure_name_available: Mock
) -> None:
    # Regression test: the availability check must run before the CLI asks for/reads a config at
    # all - otherwise a user retyping a name that's already taken wastes effort (finding a config
    # file, answering --prefix/--image-port prompts) on a request that was always going to fail.
    mock_stdin.isatty.return_value = True
    mock_ensure_name_available.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        add_command(name="brave-search", server="http://infra:8086", config=None, prefix=None, image_port=None)

    assert mock_ensure_name_available.call_args == mock.call("brave-search", "http://infra:8086")
    assert mock_info.call_count == 0
    assert mock_prompt_until_valid.call_count == 0
