# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from unittest import mock
from unittest.mock import Mock

from typer.testing import CliRunner

from deepfellow.infra.config_command.set import app, set_

SERVER = "http://localhost:9000"

runner = CliRunner()


@mock.patch("deepfellow.infra.config_command.set.echo")
@mock.patch("deepfellow.infra.config_command.set.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.set.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_set_sends_parsed_updates_to_admin_endpoint(
    mock_resolve: Mock,
    mock_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_request.return_value = {"otel_tracing_enabled": True}

    set_(updates=["otel_tracing_enabled=true"], server=None, api_key=None)

    assert mock_request.call_count == 1
    assert mock_request.call_args == mock.call(
        "PUT", f"{SERVER}/admin/config", SERVER, "the-key", json_body={"otel_tracing_enabled": True}
    )
    assert mock_echo.success.call_count == 1
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.infra.config_command.set.echo")
@mock.patch("deepfellow.infra.config_command.set.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.set.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_set_without_secret_flag_does_not_reveal(
    mock_resolve: Mock,
    mock_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_request.return_value = {
        "entries": [
            {
                "key": "DF_MESH_KEY",
                "value": "••••••••",
                "is_secret": True,
                "field_name": "mesh_key",
                "is_editable": True,
            }
        ]
    }

    set_(updates=["mesh_key=foo"], server=None, api_key=None, secret=False)

    assert mock_request.call_count == 1


@mock.patch("deepfellow.infra.config_command.set.echo")
@mock.patch("deepfellow.infra.config_command.set.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.set.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_set_with_secret_flag_reveals_secret_entries(
    mock_resolve: Mock,
    mock_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_request.side_effect = [
        {
            "entries": [
                {
                    "key": "DF_MESH_KEY",
                    "value": "••••••••",
                    "is_secret": True,
                    "field_name": "mesh_key",
                    "is_editable": True,
                },
                {"key": "DF_NAME", "value": "my-infra", "is_secret": False, "field_name": "name", "is_editable": True},
            ]
        },
        {"key": "DF_MESH_KEY", "value": "the-real-secret"},
    ]

    set_(updates=["mesh_key=foo"], server=None, api_key=None, secret=True)

    assert mock_request.call_count == 2
    assert mock_request.call_args_list[1] == mock.call(
        "GET", f"{SERVER}/admin/config/DF_MESH_KEY/reveal", SERVER, "the-key", quiet=True
    )
    printed = json.loads(mock_echo.info.call_args[0][0])
    assert printed["entries"][0]["value"] == "the-real-secret"
    assert printed["entries"][1]["value"] == "my-infra"


def test_set_cli_rejects_old_server_option():
    result = runner.invoke(app, ["otel_tracing_enabled=true", "--server", SERVER])

    assert result.exit_code == 2
    assert "no such option: --server" in result.output.lower()


@mock.patch("deepfellow.infra.config_command.set.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.set.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_set_cli_accepts_url_option(mock_resolve: Mock, mock_request: Mock):
    mock_request.return_value = {"otel_tracing_enabled": True}

    result = runner.invoke(app, ["otel_tracing_enabled=true", "--url", SERVER])

    assert result.exit_code == 0
    assert mock_resolve.call_args == mock.call(SERVER, api_key=None)
