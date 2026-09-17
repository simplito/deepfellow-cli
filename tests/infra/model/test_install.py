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

from deepfellow.infra.model.install import install as install_command
from deepfellow.infra.utils.model_install import ModelInstallConnection, apply_install, install, resolve_connection


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_raises_on_connect_error(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_success(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}

    install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_install_with_progress.call_count == 1
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Model llama-3.1-8B installed.")


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_quiet_suppresses_env_set_confirmation(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    """suite install --resume passes quiet=True (it calls this repeatedly, once per model, against
    the exact same already-confirmed connection) - the "Updated config/secrets" confirmation must
    be suppressed in that case, unlike a plain standalone `infra model install` run."""
    mock_install_with_progress.return_value = {"status": "OK"}

    install(server=None, service_name="ollama", model_name="llama-3.1-8B", quiet=True)

    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0].kwargs["quiet"] is True
    assert mock_env_set.call_args_list[1].kwargs["quiet"] is True


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_raises_when_status_not_ok(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "FAILED"}

    with pytest.raises(typer.Exit):
        install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 2
    assert mock_echo.error.call_args_list == [
        mock.call("Unable to install model."),
        mock.call("Check `docker compose logs infra` for details."),
    ]


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_exits_with_details_when_finish_status_error(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"type": "finish", "status": "error", "details": "out of memory"}

    with pytest.raises(typer.Exit):
        install(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to install model. out of memory")
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_points_to_infra_logs_when_finish_status_error_without_details(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"type": "finish", "status": "error"}

    with pytest.raises(typer.Exit):
        install(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.error.call_count == 2
    assert mock_echo.error.call_args_list == [
        mock.call("Unable to install model."),
        mock.call("Check `docker compose logs infra` for details."),
    ]
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_skips_when_model_already_installed(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    response = Mock(json=Mock(return_value={"error": {"message": "Model llama-3.1-8B on ollama already installed"}}))
    mock_install_with_progress.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)

    install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("Model 'llama-3.1-8B' is already installed; skipping.")
    assert mock_echo.error.call_count == 0
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_install_reports_success_when_infra_reports_model_already_installed_as_ok(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    # The Infra API itself treats a duplicate model install as a no-op success (status "OK"), never
    # an error - so no CLI-side skip is needed here, unlike service install.
    mock_install_with_progress.return_value = {
        "status": "OK",
        "details": "Already installed or being installed right now.",
    }

    install(server=None, service_name="ollama", model_name="llama-3.1-8B")

    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Model llama-3.1-8B installed.")
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_resolve_connection_performs_no_install_api_call(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_env_set: Mock,
) -> None:
    result = resolve_connection(server=None)

    assert result == ModelInstallConnection(server="http://infra:8086", api_key="test-key")
    assert mock_install_with_progress.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
def test_apply_install_performs_no_prompting(
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}
    connection = ModelInstallConnection(server="http://infra:8086", api_key="test-key")

    apply_install(service_name="ollama", model_name="llama-3.1-8B", connection=connection)

    assert mock_install_with_progress.call_count == 1
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.choice.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("Model llama-3.1-8B installed.")


@mock.patch("deepfellow.infra.utils.model_install.cancel_model_install")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.model_install.echo")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
def test_apply_install_cancels_install_on_keyboard_interrupt(
    mock_install_with_progress: Mock,
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_cancel: Mock,
) -> None:
    mock_install_with_progress.side_effect = KeyboardInterrupt()
    connection = ModelInstallConnection(server="http://infra:8086", api_key="test-key")

    with pytest.raises(KeyboardInterrupt):
        apply_install(service_name="ollama", model_name="llama-3.1-8B", connection=connection)

    assert mock_cancel.call_count == 1
    assert mock_cancel.call_args == mock.call("http://infra:8086", "test-key", "ollama", "llama-3.1-8B")


@mock.patch("deepfellow.infra.model.install.install_util")
def test_install_command_delegates_to_install_util(mock_install_util: Mock) -> None:
    install_command(server="http://infra:8086", service_name="ollama", model_name="llama-3.1-8B")

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(
        service_name="ollama", model_name="llama-3.1-8B", server="http://infra:8086"
    )
