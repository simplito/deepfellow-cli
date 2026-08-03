# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.state import state
from deepfellow.infra.service.list import _format_service, _is_installed, list


@pytest.fixture
def config_file() -> Mock:
    return Mock(name="config-file")


@pytest.fixture
def secrets_file() -> Mock:
    m = Mock(spec=Path, name="secrets-file")
    m.is_file.return_value = True
    return m


@pytest.fixture(autouse=True)
def default_state(config_file: Mock, secrets_file: Mock) -> None:
    state.cli_config = {"df_infra_external_url": "http://infra:8086"}
    state.cli_config_file = config_file
    state.cli_secrets_file = secrets_file


@pytest.mark.parametrize(
    ("service", "expected"),
    [
        ({"installed": False}, False),
        ({"installed": {}}, True),
        ({"installed": {"port": 1234}}, True),
        ({}, False),
    ],
)
def test_is_installed_returns_expected(service: dict[str, Any], expected: bool) -> None:
    result = _is_installed(service)

    assert result is expected


def test_format_service_formats_fields_as_key_value_lines() -> None:
    service = {
        "id": "ollama",
        "type": "llm",
        "instance": "default",
        "description": "Ollama service",
        "downloaded": True,
    }

    result = _format_service(service)

    assert result == "id: ollama\ntype: llm\ninstance: default\ndescription: Ollama service\ndownloaded: True"


@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.service.list.make_request")
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
def test_list_raises_on_connect_error(
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        list(server=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_prompts_for_server_when_not_configured(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    state.cli_config = {}
    mock_echo.prompt_until_valid.return_value = "http://prompted:8086"

    list(server=None)

    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://prompted:8086/admin/services",
        token="test-key",
        err_msg="Unable to list services.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_uses_configured_server_when_not_provided(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    list(server=None)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services",
        token="test-key",
        err_msg="Unable to list services.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_persists_server_when_changed_from_config(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    config_file: Mock,
) -> None:
    list(server="http://new:8086")

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(
        config_file, "DF_INFRA_EXTERNAL_URL", "http://new:8086", should_raise=False
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_does_not_persist_server_when_unchanged_from_config(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_prompts_for_api_key_when_missing_from_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    mock_echo.prompt.return_value = "prompted-key"

    list(server="http://infra:8086")

    assert mock_echo.prompt.call_count == 1
    assert mock_echo.prompt.call_args == mock.call("Provide Infra Admin API Key", password=True)
    assert mock_env_set.call_args == mock.call(
        secrets_file, "DF_INFRA_ADMIN_API_KEY", "prompted-key", should_raise=False
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_reads_empty_secrets_when_secrets_file_missing(
    mock_echo: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    secrets_file.is_file.return_value = False
    mock_echo.prompt.return_value = "prompted-key"

    list(server="http://infra:8086")

    assert mock_echo.prompt.call_count == 1
    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services",
        token="prompted-key",
        err_msg="Unable to list services.",
        reraise=True,
    )


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch("deepfellow.infra.service.list.make_request", return_value={"list": []})
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_prints_no_services_installed_when_list_empty(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("No services installed.")


@mock.patch("deepfellow.infra.service.list.env_set")
@mock.patch(
    "deepfellow.infra.service.list.make_request",
    return_value={
        "list": [
            {
                "id": "ollama",
                "type": "llm",
                "instance": "default",
                "description": "Ollama",
                "downloaded": True,
                "installed": {"port": 1234},
            },
            {"id": "unused", "type": "llm", "installed": False},
        ]
    },
)
@mock.patch("deepfellow.infra.service.list.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "test-key"})
@mock.patch("deepfellow.infra.service.list.echo")
def test_list_prints_only_installed_services(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_make_request: Mock,
    mock_env_set: Mock,
) -> None:
    list(server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "id: ollama\ntype: llm\ninstance: default\ndescription: Ollama\ndownloaded: True"
    )
