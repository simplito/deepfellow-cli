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

from deepfellow.common.state import state
from deepfellow.infra.utils.admin import infra_admin_request, persist_infra_admin, resolve_infra_admin

SERVER = "http://localhost:9000"


@mock.patch("deepfellow.infra.utils.admin.read_env_file")
def test_resolve_infra_admin_uses_explicit_server_and_api_key(mock_read: Mock) -> None:
    server, api_key = resolve_infra_admin(SERVER, api_key="explicit-key")

    assert server == SERVER
    assert api_key == "explicit-key"
    assert mock_read.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "stored-key"})
def test_resolve_infra_admin_uses_config_stored_server_when_none_given(mock_read: Mock, tmp_path) -> None:
    state.cli_config = {"df_infra_external_url": SERVER}
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file

    server, api_key = resolve_infra_admin(None)

    assert server == SERVER
    assert api_key == "stored-key"


@mock.patch("deepfellow.infra.utils.admin.read_env_file", return_value={"DF_INFRA_ADMIN_API_KEY": "stored-key"})
@mock.patch("deepfellow.infra.utils.admin.echo.prompt_until_valid", return_value=SERVER)
def test_resolve_infra_admin_prompts_for_server_when_not_configured(
    mock_prompt: Mock, mock_read: Mock, tmp_path
) -> None:
    state.cli_config = {}
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file

    server, _ = resolve_infra_admin(None)

    assert server == SERVER
    assert mock_prompt.call_count == 1


@mock.patch("deepfellow.infra.utils.admin.read_env_file", return_value={})
@mock.patch("deepfellow.infra.utils.admin.echo.prompt", return_value="prompted-key")
def test_resolve_infra_admin_prompts_for_api_key_when_not_stored(mock_prompt: Mock, mock_read: Mock, tmp_path) -> None:
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file

    _, api_key = resolve_infra_admin(SERVER)

    assert api_key == "prompted-key"
    assert mock_prompt.call_args == mock.call("Provide Infra Admin API Key", password=True)


@mock.patch("deepfellow.infra.utils.admin.env_set")
def test_persist_infra_admin_writes_url_and_key(mock_env_set: Mock, tmp_path) -> None:
    state.cli_config_file = tmp_path / "config"
    state.cli_secrets_file = tmp_path / "secrets"

    persist_infra_admin(SERVER, "the-key")

    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0] == mock.call(
        state.cli_config_file, "DF_INFRA_EXTERNAL_URL", SERVER, should_raise=False, quiet=False
    )
    assert mock_env_set.call_args_list[1] == mock.call(
        state.cli_secrets_file, "DF_INFRA_ADMIN_API_KEY", "the-key", should_raise=False, quiet=False
    )


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_success_persists_credentials(mock_request: Mock, mock_persist: Mock) -> None:
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "ok"}
    mock_request.return_value = mock_response

    result = infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert result == {"status": "ok"}
    assert mock_persist.call_count == 1
    assert mock_persist.call_args == mock.call(SERVER, "the-key", quiet=False)


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.echo.prompt", return_value="new-key")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_401_then_success_persists_new_key(
    mock_request: Mock, mock_prompt: Mock, mock_persist: Mock
) -> None:
    rejected = Mock(status_code=401)
    accepted = Mock(status_code=200)
    accepted.json.return_value = {"status": "ok"}
    mock_request.side_effect = [rejected, accepted]

    result = infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "stale-key")

    assert result == {"status": "ok"}
    assert mock_prompt.call_count == 1
    assert mock_persist.call_args == mock.call(SERVER, "new-key", quiet=False)


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.echo.prompt", return_value="also-bad-key")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_401_twice_raises_exit_without_persisting(
    mock_request: Mock, mock_prompt: Mock, mock_persist: Mock
) -> None:
    mock_request.return_value = Mock(status_code=401)

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "stale-key")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_connect_error_raises_exit(mock_request: Mock, mock_persist: Mock) -> None:
    mock_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_403_is_terminal_without_reprompt(mock_request: Mock, mock_persist: Mock) -> None:
    response = Mock(status_code=403)
    response.json.return_value = {"detail": "forbidden"}
    mock_request.return_value = response

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_request.call_count == 1
    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_non_dict_json_error_body_does_not_crash(mock_request: Mock, mock_persist: Mock) -> None:
    response = Mock(status_code=500)
    response.json.return_value = ["unexpected", "array", "body"]
    response.text = "raw text fallback"
    mock_request.return_value = response

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_malformed_success_body_does_not_crash(mock_request: Mock, mock_persist: Mock) -> None:
    response = Mock(status_code=200)
    response.json.side_effect = ValueError("not JSON")
    mock_request.return_value = response

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_persist.call_count == 1


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_http_error_raises_exit(mock_request: Mock, mock_persist: Mock) -> None:
    mock_request.side_effect = httpx.HTTPError("TEST")

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_persist.call_count == 0


@mock.patch("deepfellow.infra.utils.admin.persist_infra_admin")
@mock.patch("deepfellow.infra.utils.admin.httpx.request")
def test_infra_admin_request_error_body_not_json_falls_back_to_text(mock_request: Mock, mock_persist: Mock) -> None:
    response = Mock(status_code=500)
    response.json.side_effect = ValueError("not JSON")
    response.text = "raw text fallback"
    mock_request.return_value = response

    with pytest.raises(typer.Exit):
        infra_admin_request("GET", f"{SERVER}/admin/config", SERVER, "the-key")

    assert mock_persist.call_count == 0
