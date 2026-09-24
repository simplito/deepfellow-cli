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

from deepfellow.infra.service.fields import fields
from deepfellow.infra.service.install import install as install_command
from deepfellow.infra.service.list import list as list_services
from deepfellow.infra.utils.service_install import ServiceInstallSpec, apply_spec, build_spec, install


@pytest.fixture(name="name")
def name_fixture() -> str:
    return "name"


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_connection_error(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    mock_install_with_progress.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        install(name=name, spec=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_success_without_api_key(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name=name, service_api_key=None, spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {}}
    assert mock_echo.success.call_count == 1
    assert mock_env_set.call_count == 4
    assert mock_env_set.call_args_list[0].kwargs["quiet"] is False
    assert mock_env_set.call_args_list[2].kwargs["quiet"] is True


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_success_with_api_key(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name=name, service_api_key="sk-test-123", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_with_valid_spec(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name=name, spec='{"url": "http://host:11434"}')

    assert mock_get.call_count == 0
    assert mock_install_with_progress.call_count == 1
    assert mock_install_with_progress.call_args == mock.call(
        mock.ANY, mock.ANY, data={"spec": {"url": "http://host:11434"}}, message=f"Installing service {name}..."
    )
    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0].kwargs["quiet"] is False


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_with_valid_spec_and_explicit_quiet_suppresses_env_set_confirmation(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    """An explicit spec alone doesn't quiet the "Updated config/secrets" confirmation (see
    test_install_with_valid_spec above) - but suite install --resume passes quiet=True explicitly
    (it calls this repeatedly against the same already-confirmed connection), which must override
    that default regardless of whether a spec was given."""
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name=name, spec='{"url": "http://host:11434"}', quiet=True)

    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0].kwargs["quiet"] is True
    assert mock_env_set.call_args_list[1].kwargs["quiet"] is True


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_exits_with_details_when_finish_status_error(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    mock_install_with_progress.return_value = {"type": "finish", "status": "error", "details": "disk full"}

    with pytest.raises(typer.Exit):
        install(name=name, spec=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to install service. disk full")
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_points_to_infra_logs_when_finish_status_error_without_details(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    mock_install_with_progress.return_value = {"type": "finish", "status": "error"}

    with pytest.raises(typer.Exit):
        install(name=name, spec=None)

    assert mock_echo.error.call_count == 2
    assert mock_echo.error.call_args_list == [
        mock.call("Unable to install service."),
        mock.call("Check `docker compose logs infra` for details."),
    ]
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_skips_when_service_already_installed(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}
    response = Mock(
        json=Mock(return_value={"error": {"message": f"Service {name} on default instance already installed"}})
    )
    mock_install_with_progress.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    install(name=name, spec=None)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(f"Service '{name}' is already installed; skipping.")
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_build_spec_performs_no_install_api_call(
    mock_resolve: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_get.return_value = {"spec": {"fields": []}}

    result = build_spec(name=name, spec=None)

    assert result == ServiceInstallSpec(server="http://infra:8086", api_key="test-key", spec={}, explicit_spec=False)
    assert mock_install_with_progress.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_build_spec_with_explicit_spec_skips_field_resolution(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    result = build_spec(name=name, spec='{"url": "http://host:11434"}')

    assert result == ServiceInstallSpec(
        server="http://infra:8086", api_key="test-key", spec={"url": "http://host:11434"}, explicit_spec=True
    )
    assert mock_install_with_progress.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
def test_apply_spec_performs_no_prompting(
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}
    install_spec = ServiceInstallSpec(
        server="http://infra:8086", api_key="test-key", spec={"url": "http://host:11434"}, explicit_spec=True
    )

    apply_spec(name, install_spec)

    assert mock_install_with_progress.call_count == 1
    assert mock_install_with_progress.call_args == mock.call(
        "http://infra:8086/admin/services/name",
        "test-key",
        data={"spec": {"url": "http://host:11434"}},
        message="Installing service name...",
    )
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.choice.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
def test_apply_spec_skips_when_service_already_installed(
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    response = Mock(
        json=Mock(return_value={"error": {"message": f"Service {name} on default instance already installed"}})
    )
    mock_install_with_progress.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    install_spec = ServiceInstallSpec(server="http://infra:8086", api_key="test-key", spec={}, explicit_spec=True)

    apply_spec(name, install_spec)

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(f"Service '{name}' is already installed; skipping.")


@mock.patch("deepfellow.infra.utils.service_install.cancel_service_install")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
def test_apply_spec_cancels_install_on_keyboard_interrupt(
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_cancel: Mock,
    name: str,
) -> None:
    mock_install_with_progress.side_effect = KeyboardInterrupt()
    install_spec = ServiceInstallSpec(server="http://infra:8086", api_key="test-key", spec={}, explicit_spec=True)

    with pytest.raises(KeyboardInterrupt):
        apply_spec(name, install_spec)

    assert mock_cancel.call_count == 1
    assert mock_cancel.call_args == mock.call("http://infra:8086", "test-key", name)


def test_install_with_invalid_json_spec(name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec="not-json")


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_install_with_non_object_json_spec(mock_echo: Mock, name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec='["a", "b"]')

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--spec must be a JSON object, not an array or scalar.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch("deepfellow.infra.utils.fields.is_interactive", return_value=False)
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_claude_with_api_key(
    mock_resolve: Mock,
    mock_is_interactive: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_get.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "api_key",
                    "type": "password",
                    "required": True,
                    "description": "API Key",
                    "default": None,
                    "values": None,
                },
                {
                    "name": "api_url",
                    "type": "text",
                    "required": False,
                    "description": "API URL",
                    "default": "https://api.anthropic.com",
                    "values": None,
                },
                {
                    "name": "anthropic_version",
                    "type": "text",
                    "required": True,
                    "description": "Anthropic API Version",
                    "default": "2023-06-01",
                    "values": None,
                },
            ]
        }
    }
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="claude", service_api_key="sk-test-123", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "sk-test-123", "anthropic_version": "2023-06-01"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch("deepfellow.infra.utils.fields.is_interactive", return_value=False)
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_google_with_api_key(
    mock_resolve: Mock,
    mock_is_interactive: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_get.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "api_url",
                    "type": "text",
                    "required": False,
                    "description": "API URL",
                    "default": "https://generativelanguage.googleapis.com",
                    "values": None,
                },
                {
                    "name": "api_key",
                    "type": "password",
                    "required": False,
                    "description": "API Key",
                    "default": "",
                    "values": None,
                },
            ]
        }
    }
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="google", service_api_key="google-key-123", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "google-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch("deepfellow.infra.utils.fields.is_interactive", return_value=False)
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_openai_with_api_key(
    mock_resolve: Mock,
    mock_is_interactive: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_get.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "api_url",
                    "type": "text",
                    "required": False,
                    "description": "API URL",
                    "default": "https://api.openai.com",
                    "values": None,
                },
                {
                    "name": "api_key",
                    "type": "password",
                    "required": False,
                    "description": "API Key",
                    "default": "",
                    "values": None,
                },
            ]
        }
    }
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="openai", service_api_key="openai-key-123", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "openai-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.service_install.echo")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_install.get")
@mock.patch("deepfellow.infra.utils.fields.is_interactive", return_value=False)
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_sindri_with_api_key(
    mock_resolve: Mock,
    mock_is_interactive: Mock,
    mock_get: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_get.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "api_url",
                    "type": "text",
                    "required": False,
                    "description": "API URL",
                    "default": "https://sindri.app/api/ai/v1/openai",
                    "values": None,
                },
                {
                    "name": "api_key",
                    "type": "password",
                    "required": True,
                    "description": "API Key",
                    "default": None,
                    "values": None,
                },
            ]
        }
    }
    mock_install_with_progress.return_value = {"status": "OK"}

    install(name="sindri", service_api_key="sindri-key-123", spec=None)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "sindri-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.service_install.echo")
def test_install_raises_when_spec_is_blank(mock_echo: Mock, name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec="   ")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--spec cannot be empty.")


@mock.patch("deepfellow.infra.utils.service_install.echo")
def test_install_raises_when_spec_and_set_args_given_together(mock_echo: Mock, name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec='{"a": "b"}', set_args=["a=b"])

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--spec and --set cannot be used together. Use one or the other.")


@mock.patch("deepfellow.infra.service.install.install_util")
def test_install_command_delegates_to_install_util(
    mock_install_util: Mock,
    name: str,
) -> None:
    install_command(
        server="http://infra:8086",
        name=name,
        service_api_key="sk-test-123",
        spec=None,
        set_args=None,
        prompt_all=True,
    )

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(
        name=name,
        server="http://infra:8086",
        service_api_key="sk-test-123",
        spec=None,
        set_args=None,
        prompt_all=True,
    )


@mock.patch("deepfellow.infra.service.list.echo")
@mock.patch("deepfellow.infra.service.list.make_request")
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_displays_services(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {
        "list": [
            {
                "id": "ollama",
                "type": "ollama",
                "instance": "default",
                "description": "Local models.",
                "downloaded": True,
                "installed": {"hardware": "CPU"},
            },
            {
                "id": "vllm",
                "type": "vllm",
                "instance": "default",
                "description": "High-throughput model server.",
                "downloaded": False,
                "installed": False,
            },
        ]
    }

    list_services(server="http://infra:8086")

    assert mock_make_request.call_count == 1
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "id: ollama\ntype: ollama\ninstance: default\ndescription: Local models.\ndownloaded: True"
    )


@mock.patch("deepfellow.infra.service.list.echo")
@mock.patch("deepfellow.infra.service.list.make_request")
@mock.patch("deepfellow.infra.service.list.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_list_with_no_installed_services(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
) -> None:
    mock_make_request.return_value = {"list": [{"id": "claude", "installed": False}]}

    list_services(server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("No services installed.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_displays_fields(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "url",
                    "description": "URL to external Ollama instance",
                    "default": "http://localhost:11434",
                }
            ]
        }
    }

    fields(name="ollama-external", set_format=False, server="http://infra:8086")

    assert mock_make_request.call_count == 1
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "- url: URL to external Ollama instance (default: http://localhost:11434)"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_missing_default_shows_none(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {"spec": {"fields": [{"name": "token", "description": "API token"}]}}

    fields(name="some-service", set_format=False, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("- token: API token (default: None)")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_with_no_fields(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    name: str,
) -> None:
    mock_make_request.return_value = {"spec": {"fields": []}}

    fields(name=name, set_format=False, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(f"Service '{name}' has no configuration fields.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_oneof_lists_available_options(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "hardware",
                    "description": "Choose hardware:",
                    "default": "GPU",
                    "values": [{"value": "GPU", "label": "GPU"}, {"value": "CPU", "label": "CPU"}],
                }
            ]
        }
    }

    fields(name="ollama", set_format=False, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("- hardware: Choose hardware: (default: GPU, available: GPU, CPU)")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_set_displays_set_usage_hints(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "hardware",
                    "description": "Choose hardware:",
                    "default": "GPU",
                    "required": True,
                }
            ]
        }
    }

    fields(name="ollama", set_format=True, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "  --set hardware=<value>  (required)  Choose hardware:  (default: GPU)"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_set_missing_default_omits_default(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {"spec": {"fields": [{"name": "token", "description": "API token"}]}}

    fields(name="some-service", set_format=True, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("  --set token=<value>  (optional)  API token")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.service.fields.echo")
@mock.patch("deepfellow.infra.service.fields.make_request")
@mock.patch("deepfellow.infra.service.fields.resolve_infra_connection", return_value=("http://infra:8086", "test-key"))
def test_fields_set_oneof_lists_available_options(
    mock_resolve: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_make_request.return_value = {
        "spec": {
            "fields": [
                {
                    "name": "hardware",
                    "description": "Choose hardware:",
                    "default": "GPU",
                    "required": True,
                    "values": [{"value": "GPU", "label": "GPU"}, {"value": "CPU", "label": "CPU"}],
                }
            ]
        }
    }

    fields(name="ollama", set_format=True, server="http://infra:8086")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "  --set hardware=<value>  (required)  Choose hardware:  (default: GPU, available: GPU, CPU)"
    )
