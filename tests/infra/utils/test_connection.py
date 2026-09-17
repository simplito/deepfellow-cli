# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from json import JSONDecodeError
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest
import typer

from deepfellow.common.exceptions import InfraInstallSkippedError
from deepfellow.common.state import state
from deepfellow.infra.utils.connection import (
    INSTALL_RETRY_INTERVAL_SECONDS,
    _error_message,
    call_infra,
    cancel_model_install,
    cancel_on_interrupt,
    cancel_service_install,
    persist_infra_connection,
    resolve_infra_connection,
)


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
    state.cli_config_file = config_file
    state.cli_secrets_file = secrets_file
    state.cli_config = {}


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_uses_provided_server_and_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "existing-key"
    assert mock_read_env_file.call_count == 1
    assert mock_read_env_file.call_args == mock.call(secrets_file)
    assert mock_env_set.call_count == 0
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_reuses_matching_config_server(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
) -> None:
    state.cli_config = {"df_infra_external_url": "http://infra:8086"}
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "existing-key"
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_falls_back_to_config_server_when_none_given(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
) -> None:
    state.cli_config = {"df_infra_external_url": "http://config-infra:8086"}
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection(None)

    assert server == "http://config-infra:8086"
    assert api_key == "existing-key"
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_server_when_none_available(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
) -> None:
    mock_echo.prompt_until_valid.return_value = "http://prompted-infra:8086"
    mock_read_env_file.return_value = {"DF_INFRA_ADMIN_API_KEY": "existing-key"}

    server, api_key = resolve_infra_connection(None)

    assert server == "http://prompted-infra:8086"
    assert api_key == "existing-key"
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_api_key_when_secrets_file_missing(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
    secrets_file: Mock,
) -> None:
    secrets_file.is_file.return_value = False
    mock_echo.prompt.return_value = "prompted-key"

    server, api_key = resolve_infra_connection("http://infra:8086")

    assert server == "http://infra:8086"
    assert api_key == "prompted-key"
    assert mock_read_env_file.call_count == 0
    assert mock_echo.prompt.call_count == 1
    assert mock_echo.prompt.call_args == mock.call("Provide Infra Admin API Key", password=True)
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.connection.read_env_file")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_resolve_infra_connection_prompts_for_api_key_when_not_in_secrets(
    mock_echo: Mock,
    mock_read_env_file: Mock,
    mock_env_set: Mock,
) -> None:
    mock_read_env_file.return_value = {}
    mock_echo.prompt.return_value = "prompted-key"

    _, api_key = resolve_infra_connection("http://infra:8086")

    assert api_key == "prompted-key"
    assert mock_echo.prompt.call_count == 1
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.env_set")
def test_persist_infra_connection_writes_url_and_key(mock_env_set: Mock, config_file: Mock, secrets_file: Mock) -> None:
    persist_infra_connection("http://infra:8086", "the-key")

    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0] == mock.call(
        config_file, "DF_INFRA_EXTERNAL_URL", "http://infra:8086", should_raise=False, quiet=False
    )
    assert mock_env_set.call_args_list[1] == mock.call(
        secrets_file, "DF_INFRA_ADMIN_API_KEY", "the-key", should_raise=False, quiet=False
    )


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_returns_request_result(mock_echo: Mock) -> None:
    request = Mock(return_value={"status": "OK"})

    result = call_infra(request, "Unable to call Infra")

    assert result == {"status": "OK"}
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_persists_on_success_when_server_and_api_key_given(mock_echo: Mock, mock_persist: Mock) -> None:
    request = Mock(return_value={"status": "OK"})

    result = call_infra(request, "Unable to call Infra", server="http://infra:8086", api_key="the-key")

    assert result == {"status": "OK"}
    assert mock_persist.call_count == 1
    assert mock_persist.call_args == mock.call("http://infra:8086", "the-key", quiet=False)


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_does_not_persist_without_server_and_api_key(mock_echo: Mock, mock_persist: Mock) -> None:
    request = Mock(return_value={"status": "OK"})

    call_infra(request, "Unable to call Infra")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_does_not_persist_on_connect_error(mock_echo: Mock, mock_persist: Mock) -> None:
    request = Mock(side_effect=httpx.ConnectError("TEST"))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra", server="http://infra:8086", api_key="the-key")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_raises_on_connect_error(mock_echo: Mock) -> None:
    request = Mock(side_effect=httpx.ConnectError("TEST"))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_response_text_on_http_status_error(mock_echo: Mock) -> None:
    response = Mock(json=Mock(side_effect=JSONDecodeError("Expecting value", "", 0)), text="Service not found")
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service not found")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_default_message_when_response_has_no_body(mock_echo: Mock) -> None:
    response = Mock(json=Mock(side_effect=JSONDecodeError("Expecting value", "", 0)), text="")
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to call Infra")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_prefers_detail_from_json_body_on_http_status_error(mock_echo: Mock) -> None:
    response = Mock(json=Mock(return_value={"detail": "Service 'foo' already exists"}), text='{"detail": "..."}')
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service 'foo' already exists")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_falls_back_to_text_when_body_is_not_json(mock_echo: Mock) -> None:
    response = Mock(json=Mock(side_effect=JSONDecodeError("Expecting value", "", 0)), text="Internal Server Error")
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Internal Server Error")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_prefers_error_message_from_json_body_on_http_status_error(mock_echo: Mock) -> None:
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installed"}}),
        text='{"error": {"message": "..."}}',
    )
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service ollama on default instance already installed")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_falls_back_to_detail_when_error_object_has_no_message(mock_echo: Mock) -> None:
    response = Mock(
        json=Mock(return_value={"error": {}, "detail": "Service 'foo' already exists"}),
        text='{"error": {}, "detail": "..."}',
    )
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service 'foo' already exists")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_default_message_when_detail_is_a_fastapi_validation_error_list(mock_echo: Mock) -> None:
    response = Mock(
        json=Mock(return_value={"detail": [{"loc": ["query", "model_id"], "msg": "field required"}]}),
        text='{"detail": [...]}',
    )
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to call Infra")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_default_message_when_json_body_has_neither_error_nor_detail(mock_echo: Mock) -> None:
    response = Mock(json=Mock(return_value={"foo": "bar"}), text='{"foo": "bar"}')
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to call Infra")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_falls_back_to_text_when_json_body_is_not_a_dict(mock_echo: Mock) -> None:
    response = Mock(json=Mock(return_value=["unexpected", "list"]), text='["unexpected", "list"]')
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call('["unexpected", "list"]')


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_raises_infra_install_skipped_when_message_matches(mock_echo: Mock) -> None:
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installed"}})
    )
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(InfraInstallSkippedError) as exc_info:
        call_infra(request, "Unable to call Infra", skip_if_message_contains="already installed")

    assert str(exc_info.value) == "Service ollama on default instance already installed"
    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_does_not_skip_when_message_does_not_match(mock_echo: Mock) -> None:
    response = Mock(json=Mock(return_value={"error": {"message": "Out of disk space"}}))
    request = Mock(side_effect=httpx.HTTPStatusError("TEST", request=Mock(), response=response))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra", skip_if_message_contains="already installed")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Out of disk space")


@mock.patch("deepfellow.infra.utils.connection.time")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_retries_and_succeeds_when_message_matches_retry(mock_echo: Mock, mock_time: Mock) -> None:
    """A job some other (likely interrupted) run left installing server-side must be waited out,
    not treated as a hard failure - the very bug behind DFCLI-60's --resume/ollama report."""
    mock_time.monotonic.side_effect = [0, 0, 0]
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installing"}})
    )
    error = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    request = Mock(side_effect=[error, {"status": "ok"}])

    result = call_infra(request, "Unable to call Infra", retry_if_message_contains="already installing")

    assert result == {"status": "ok"}
    assert request.call_count == 2
    assert mock_time.sleep.call_count == 1
    assert mock_time.sleep.call_args == mock.call(INSTALL_RETRY_INTERVAL_SECONDS)
    assert mock_echo.error.call_count == 0
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call(
        "Service ollama on default instance already installing; waiting for it to finish before retrying..."
    )


@mock.patch("deepfellow.infra.utils.connection.time")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_prints_still_waiting_on_subsequent_retries(mock_echo: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 0, 5, 10]
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installing"}})
    )
    error = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    request = Mock(side_effect=[error, error, {"status": "ok"}])

    result = call_infra(request, "Unable to call Infra", retry_if_message_contains="already installing")

    assert result == {"status": "ok"}
    assert request.call_count == 3
    assert mock_time.sleep.call_count == 2
    assert mock_echo.info.call_count == 2
    assert mock_echo.info.call_args_list[1] == mock.call("Still waiting... (10s)")


@mock.patch("deepfellow.infra.utils.connection.time")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_gives_up_retrying_once_deadline_has_passed(mock_echo: Mock, mock_time: Mock) -> None:
    mock_time.monotonic.side_effect = [0, 0, 999_999]
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installing"}})
    )
    error = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    request = Mock(side_effect=error)

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra", retry_if_message_contains="already installing")

    assert request.call_count == 1
    assert mock_time.sleep.call_count == 0
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Service ollama on default instance already installing")


@mock.patch("deepfellow.infra.utils.connection.time")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_skip_takes_precedence_over_retry_when_both_match(mock_echo: Mock, mock_time: Mock) -> None:
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installed"}})
    )
    error = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    request = Mock(side_effect=error)

    with pytest.raises(InfraInstallSkippedError):
        call_infra(
            request,
            "Unable to call Infra",
            skip_if_message_contains="already installed",
            retry_if_message_contains="already installing",
        )

    assert request.call_count == 1
    assert mock_time.sleep.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_call_infra_shows_default_message_on_generic_http_error(mock_echo: Mock) -> None:
    request = Mock(side_effect=httpx.ReadTimeout("timed out"))

    with pytest.raises(typer.Exit):
        call_infra(request, "Unable to call Infra")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Unable to call Infra")


def test_cancel_on_interrupt_returns_call_result_when_not_interrupted() -> None:
    call = Mock(return_value={"status": "ok"})
    cancel = Mock()

    result = cancel_on_interrupt(call, cancel, "service 'ollama'")

    assert result == {"status": "ok"}
    assert cancel.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_on_interrupt_cancels_and_reraises_on_keyboard_interrupt(mock_echo: Mock) -> None:
    call = Mock(side_effect=KeyboardInterrupt())
    cancel = Mock()

    with pytest.raises(KeyboardInterrupt):
        cancel_on_interrupt(call, cancel, "service 'ollama'")

    assert cancel.call_count == 1
    assert mock_echo.warning.call_count == 1
    assert mock_echo.warning.call_args == mock.call("Interrupted; cancelling service 'ollama' install on Infra...")


@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_on_interrupt_keeps_the_original_interrupt_when_cancel_itself_raises(mock_echo: Mock) -> None:
    """cancel() blowing up (e.g. httpx.InvalidURL, a bug in the cancel helper) must never replace the
    KeyboardInterrupt with its own traceback - the interrupt is still what the user asked for."""
    call = Mock(side_effect=KeyboardInterrupt())
    cancel = Mock(side_effect=ValueError("boom"))

    with pytest.raises(KeyboardInterrupt):
        cancel_on_interrupt(call, cancel, "service 'ollama'")

    assert cancel.call_count == 1
    assert mock_echo.warning.call_count == 2
    assert mock_echo.warning.call_args_list[0] == mock.call(
        "Interrupted; cancelling service 'ollama' install on Infra..."
    )
    assert mock_echo.warning.call_args_list[1] == mock.call(
        "Could not cancel service 'ollama' install on Infra; it may still be running there. (boom)"
    )


def test_cancel_on_interrupt_lets_other_exceptions_propagate_without_cancelling() -> None:
    call = Mock(side_effect=ValueError("boom"))
    cancel = Mock()

    with pytest.raises(ValueError, match="boom"):
        cancel_on_interrupt(call, cancel, "service 'ollama'")

    assert cancel.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_service_install_posts_to_cancel_endpoint(mock_echo: Mock, mock_post: Mock) -> None:
    mock_post.return_value = Mock(status_code=200)

    cancel_service_install("http://infra:8086", "the-key", "ollama")

    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "http://infra:8086/admin/services/ollama/cancel",
        headers={"Authorization": "Bearer the-key"},
        timeout=30.0,
    )
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_service_install_swallows_not_installing_404(mock_echo: Mock, mock_post: Mock) -> None:
    mock_post.return_value = Mock(status_code=404)

    cancel_service_install("http://infra:8086", "the-key", "ollama")

    assert mock_echo.warning.call_count == 0
    assert mock_echo.debug.call_args == mock.call("service 'ollama': nothing was installing (404); nothing to cancel.")


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_service_install_warns_on_other_error(mock_echo: Mock, mock_post: Mock) -> None:
    response = Mock(status_code=405)
    response.raise_for_status.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    mock_post.return_value = response

    cancel_service_install("http://infra:8086", "the-key", "ollama")

    assert mock_echo.warning.call_count == 1
    assert "service 'ollama'" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_model_install_posts_to_cancel_endpoint_with_model_id(mock_echo: Mock, mock_post: Mock) -> None:
    mock_post.return_value = Mock(status_code=200)

    cancel_model_install("http://infra:8086", "the-key", "ollama", "llama3")

    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "http://infra:8086/admin/services/ollama/models/cancel?model_id=llama3",
        headers={"Authorization": "Bearer the-key"},
        timeout=30.0,
    )
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_model_install_swallows_not_installing_404(mock_echo: Mock, mock_post: Mock) -> None:
    mock_post.return_value = Mock(status_code=404)

    cancel_model_install("http://infra:8086", "the-key", "ollama", "llama3")

    assert mock_echo.warning.call_count == 0
    assert mock_echo.debug.call_args == mock.call("model 'llama3': nothing was installing (404); nothing to cancel.")


@mock.patch("deepfellow.infra.utils.connection.httpx.post")
@mock.patch("deepfellow.infra.utils.connection.echo")
def test_cancel_model_install_warns_on_other_error(mock_echo: Mock, mock_post: Mock) -> None:
    response = Mock(status_code=500)
    response.raise_for_status.side_effect = httpx.HTTPStatusError("TEST", request=Mock(), response=response)
    mock_post.return_value = response

    cancel_model_install("http://infra:8086", "the-key", "ollama", "llama3")

    assert mock_echo.warning.call_count == 1
    assert "model 'llama3'" in mock_echo.warning.call_args.args[0]


def test_error_message_returns_error_message_from_json_body() -> None:
    response = Mock(
        json=Mock(return_value={"error": {"message": "Service ollama on default instance already installed"}})
    )

    message = _error_message(response, "Unable to call Infra")

    assert message == "Service ollama on default instance already installed"


def test_error_message_falls_back_to_detail_when_error_object_has_no_message() -> None:
    response = Mock(json=Mock(return_value={"error": {}, "detail": "Service 'foo' already exists"}))

    message = _error_message(response, "Unable to call Infra")

    assert message == "Service 'foo' already exists"


def test_error_message_returns_default_when_json_body_has_neither_error_nor_detail() -> None:
    response = Mock(json=Mock(return_value={"foo": "bar"}))

    message = _error_message(response, "Unable to call Infra")

    assert message == "Unable to call Infra"


def test_error_message_falls_back_to_text_when_body_is_not_json() -> None:
    response = Mock(json=Mock(side_effect=JSONDecodeError("Expecting value", "", 0)), text="Internal Server Error")

    message = _error_message(response, "Unable to call Infra")

    assert message == "Internal Server Error"


def test_error_message_falls_back_to_text_when_json_body_is_not_a_dict() -> None:
    response = Mock(json=Mock(return_value=["unexpected", "list"]), text='["unexpected", "list"]')

    message = _error_message(response, "Unable to call Infra")

    assert message == '["unexpected", "list"]'


def test_error_message_returns_default_when_body_is_not_json_and_text_is_empty() -> None:
    response = Mock(json=Mock(side_effect=JSONDecodeError("Expecting value", "", 0)), text="")

    message = _error_message(response, "Unable to call Infra")

    assert message == "Unable to call Infra"


def test_error_message_returns_default_when_detail_is_a_fastapi_validation_error_list() -> None:
    response = Mock(json=Mock(return_value={"detail": [{"loc": ["query", "model_id"], "msg": "field required"}]}))

    message = _error_message(response, "Unable to call Infra")

    assert message == "Unable to call Infra"
