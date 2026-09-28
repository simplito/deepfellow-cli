# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from typer.testing import CliRunner

from deepfellow.infra.config_command.get import app, get_

SERVER = "http://localhost:9000"

runner = CliRunner()


@mock.patch("deepfellow.infra.config_command.get.echo")
@mock.patch("deepfellow.infra.config_command.get.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.get.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_get_prints_config_from_admin_endpoint(
    mock_resolve: Mock,
    mock_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_request.return_value = {"otel_tracing_enabled": True}

    get_(server=None, api_key=None)

    assert mock_request.call_count == 1
    assert mock_request.call_args == mock.call("GET", f"{SERVER}/admin/config", SERVER, "the-key")
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.infra.config_command.get.echo")
@mock.patch("deepfellow.infra.config_command.get.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.get.resolve_infra_admin", return_value=(SERVER, "explicit-key"))
def test_get_passes_server_and_api_key_to_resolve(
    mock_resolve: Mock,
    mock_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_request.return_value = {}

    get_(server=SERVER, api_key="explicit-key")

    assert mock_resolve.call_args == mock.call(SERVER, api_key="explicit-key")


@mock.patch("deepfellow.infra.config_command.get.echo")
@mock.patch("deepfellow.infra.config_command.get.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.get.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_get_without_secret_flag_does_not_reveal(
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

    get_(server=None, api_key=None, secret=False)

    assert mock_request.call_count == 1
    assert mock_echo.info.call_args == mock.call("DF_MESH_KEY (mesh_key): ••••••••")


@mock.patch("deepfellow.infra.config_command.get.echo")
@mock.patch("deepfellow.infra.config_command.get.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.get.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_get_with_secret_flag_reveals_secret_entries(
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

    get_(server=None, api_key=None, secret=True)

    assert mock_request.call_count == 2
    assert mock_request.call_args_list[1] == mock.call(
        "GET", f"{SERVER}/admin/config/DF_MESH_KEY/reveal", SERVER, "the-key", quiet=True
    )
    assert mock_echo.info.call_args == mock.call("DF_MESH_KEY (mesh_key): the-real-secret\nDF_NAME (name): my-infra")


def test_get_cli_rejects_old_server_option():
    result = runner.invoke(app, ["--server", SERVER])

    assert result.exit_code == 2
    assert "no such option: --server" in result.output.lower()


@mock.patch("deepfellow.infra.config_command.get.infra_admin_request")
@mock.patch("deepfellow.infra.config_command.get.resolve_infra_admin", return_value=(SERVER, "the-key"))
def test_get_cli_accepts_url_option(mock_resolve: Mock, mock_request: Mock):
    mock_request.return_value = {"entries": []}

    result = runner.invoke(app, ["--url", SERVER])

    assert result.exit_code == 0
    assert mock_resolve.call_args == mock.call(SERVER, api_key=None)
