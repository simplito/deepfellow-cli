# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the rest module."""

from json import JSONDecodeError
from pathlib import Path
from unittest import mock

import httpx
import pytest
import typer

from deepfellow.common.rest import check_health, delete, get, get_server_url, make_request, post
from deepfellow.common.state import state

URL = "http://example.com/items/1"
TOKEN = "some-token"


def _mock_response(status_code: int, json_data: dict | None = None, raises: Exception | None = None) -> mock.Mock:
    response = mock.Mock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    if raises is not None:
        response.raise_for_status.side_effect = raises
    return response


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_calls_env_set_when_config_file_set_and_no_existing_server(
    mock_env_set: mock.Mock, mock_check_health: mock.Mock
):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {}

    get_server_url("http://example.com")

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == mock.call(
        Path("/fake/.env"), "SERVER_URL", "http://example.com", should_raise=False, docker_note=False
    )


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_uses_config_server_when_none_provided(mock_env_set: mock.Mock, mock_check_health: mock.Mock):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {"df_server_url": "http://config.example.com"}

    result = get_server_url(None)

    assert result == "http://config.example.com"
    assert mock_env_set.call_count == 0
    assert mock_check_health.call_args == mock.call("http://config.example.com")


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.echo.prompt")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_prompts_when_no_server_and_no_config(
    mock_env_set: mock.Mock, mock_prompt: mock.Mock, mock_check_health: mock.Mock
):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {}
    mock_prompt.return_value = "http://prompted.example.com"

    result = get_server_url(None)

    assert result == "http://prompted.example.com"
    assert mock_prompt.call_count == 1
    assert mock_env_set.call_count == 1


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.echo.prompt")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_retries_prompt_after_bad_parameter(
    mock_env_set: mock.Mock, mock_prompt: mock.Mock, mock_error: mock.Mock, mock_check_health: mock.Mock
):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {}
    mock_prompt.side_effect = [typer.BadParameter("invalid"), "http://retried.example.com"]

    result = get_server_url(None)

    assert result == "http://retried.example.com"
    assert mock_prompt.call_count == 2
    assert mock_error.call_count == 1


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.echo.confirm")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_saves_new_server_when_confirmed(
    mock_env_set: mock.Mock, mock_confirm: mock.Mock, mock_check_health: mock.Mock
):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {"df_server_url": "http://old.example.com"}
    mock_confirm.return_value = True

    result = get_server_url("http://new.example.com")

    assert result == "http://new.example.com"
    assert mock_confirm.call_count == 1
    assert mock_env_set.call_count == 1


@mock.patch("deepfellow.common.rest.check_health")
@mock.patch("deepfellow.common.rest.echo.confirm")
@mock.patch("deepfellow.common.rest.env_set")
def test_get_server_url_keeps_new_server_without_saving_when_not_confirmed(
    mock_env_set: mock.Mock, mock_confirm: mock.Mock, mock_check_health: mock.Mock
):
    state.cli_config_file = Path("/fake/.env")
    state.cli_config = {"df_server_url": "http://old.example.com"}
    mock_confirm.return_value = False

    result = get_server_url("http://new.example.com")

    assert result == "http://new.example.com"
    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_returns_json_on_success(mock_get: mock.Mock):
    mock_get.return_value = _mock_response(200, json_data={"id": "1"})

    result = get(URL, TOKEN)

    assert result == {"id": "1"}
    assert mock_get.call_args == mock.call(URL, headers={"Authorization": f"Bearer {TOKEN}"})


@pytest.mark.parametrize("status_code", [400, 404, 422])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_not_found_status_raises_exit(mock_get: mock.Mock, mock_error: mock.Mock, status_code: int):
    mock_get.return_value = _mock_response(status_code)

    with pytest.raises(typer.Exit):
        get(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Widget not found.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_forbidden_with_json_error_message_raises_exit(mock_get: mock.Mock, mock_error: mock.Mock):
    mock_get.return_value = _mock_response(403, json_data={"error": {"message": "no access"}})

    with pytest.raises(typer.Exit):
        get(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to get Widget. no access.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_forbidden_with_json_detail_raises_exit(mock_get: mock.Mock, mock_error: mock.Mock):
    mock_get.return_value = _mock_response(403, json_data={"detail": "no access"})

    with pytest.raises(typer.Exit):
        get(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to get Widget. no access.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_forbidden_with_null_error_falls_back_to_detail(mock_get: mock.Mock, mock_error: mock.Mock):
    mock_get.return_value = _mock_response(403, json_data={"error": None, "detail": "no access"})

    with pytest.raises(typer.Exit):
        get(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to get Widget. no access.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_forbidden_with_non_json_body_uses_response_text(mock_get: mock.Mock, mock_error: mock.Mock):
    response = _mock_response(403)
    response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    response.text = "plain text error"
    mock_get.return_value = response

    with pytest.raises(typer.Exit):
        get(URL, TOKEN)

    assert mock_error.call_args == mock.call("Unable to get Item. plain text error.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_http_error_raises_exit_by_default(mock_get: mock.Mock, mock_error: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_get.return_value = _mock_response(500, raises=error)

    with pytest.raises(typer.Exit):
        get(URL, TOKEN)

    assert mock_error.call_args == mock.call("HTTP Exception")


@mock.patch("deepfellow.common.rest.httpx.get")
def test_get_http_error_reraises_when_reraise_true(mock_get: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_get.return_value = _mock_response(500, raises=error)

    with pytest.raises(httpx.HTTPStatusError):
        get(URL, TOKEN, reraise=True)


@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_succeeds_without_return_value(mock_delete: mock.Mock):
    mock_delete.return_value = _mock_response(204)

    delete(URL, TOKEN)

    assert mock_delete.call_args == mock.call(URL, headers={"Authorization": f"Bearer {TOKEN}"})


@pytest.mark.parametrize("status_code", [400, 404, 422])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_not_found_status_raises_exit(mock_delete: mock.Mock, mock_error: mock.Mock, status_code: int):
    mock_delete.return_value = _mock_response(status_code)

    with pytest.raises(typer.Exit):
        delete(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Widget not found.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_forbidden_with_json_error_message_raises_exit(mock_delete: mock.Mock, mock_error: mock.Mock):
    mock_delete.return_value = _mock_response(403, json_data={"error": {"message": "no access"}})

    with pytest.raises(typer.Exit):
        delete(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to delete the Widget. no access.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_forbidden_with_json_detail_raises_exit(mock_delete: mock.Mock, mock_error: mock.Mock):
    mock_delete.return_value = _mock_response(403, json_data={"detail": "no access"})

    with pytest.raises(typer.Exit):
        delete(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to delete the Widget. no access.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_forbidden_with_non_json_body_uses_response_text(mock_delete: mock.Mock, mock_error: mock.Mock):
    response = _mock_response(403)
    response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    response.text = "plain text error"
    mock_delete.return_value = response

    with pytest.raises(typer.Exit):
        delete(URL, TOKEN)

    assert mock_error.call_args == mock.call("Unable to delete the Item. plain text error.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.delete")
def test_delete_http_error_raises_exit(mock_delete: mock.Mock, mock_error: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_delete.return_value = _mock_response(500, raises=error)

    with pytest.raises(typer.Exit):
        delete(URL, TOKEN)

    assert mock_error.call_args == mock.call("HTTP Exception")


@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_returns_json_on_success(mock_post: mock.Mock):
    mock_post.return_value = _mock_response(200, json_data={"id": "1"})

    result = post(URL, TOKEN, data={"name": "widget"})

    assert result == {"id": "1"}
    assert mock_post.call_args == mock.call(
        URL, headers={"Authorization": f"Bearer {TOKEN}"}, json={"name": "widget"}, timeout=60 * 60 * 24
    )


@pytest.mark.parametrize("status_code", [400, 401, 403])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_client_error_message_status_raises_exit(mock_post: mock.Mock, mock_error: mock.Mock, status_code: int):
    mock_post.return_value = _mock_response(status_code, json_data={"error": {"message": "bad request"}})

    with pytest.raises(typer.Exit):
        post(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to create Widget. bad request.")


@pytest.mark.parametrize("status_code", [400, 401, 403])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_client_error_detail_status_raises_exit(mock_post: mock.Mock, mock_error: mock.Mock, status_code: int):
    mock_post.return_value = _mock_response(status_code, json_data={"detail": "bad request"})

    with pytest.raises(typer.Exit):
        post(URL, TOKEN, item_name="Widget")

    assert mock_error.call_args == mock.call("Unable to create Widget. bad request.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_client_error_with_non_json_body_uses_response_text(mock_post: mock.Mock, mock_error: mock.Mock):
    response = _mock_response(400)
    response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    response.text = "plain text error"
    mock_post.return_value = response

    with pytest.raises(typer.Exit):
        post(URL, TOKEN)

    assert mock_error.call_args == mock.call("Unable to create Item. plain text error.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_http_error_raises_exit_by_default(mock_post: mock.Mock, mock_error: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_post.return_value = _mock_response(500, raises=error)

    with pytest.raises(typer.Exit):
        post(URL, TOKEN)

    assert mock_error.call_args == mock.call("HTTP Exception")


@mock.patch("deepfellow.common.rest.httpx.post")
def test_post_http_error_reraises_when_reraise_true(mock_post: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_post.return_value = _mock_response(500, raises=error)

    with pytest.raises(httpx.HTTPStatusError):
        post(URL, TOKEN, reraise=True)


@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_returns_json_on_success(mock_request: mock.Mock):
    mock_request.return_value = _mock_response(200, json_data={"id": "1"})

    result = make_request("PATCH", URL, TOKEN, data={"name": "widget"})

    assert result == {"id": "1"}
    assert mock_request.call_args == mock.call(
        method="PATCH",
        url=URL,
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"name": "widget"},
        timeout=60 * 60 * 24,
    )


@pytest.mark.parametrize("status_code", [400, 401, 403])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_client_error_message_status_raises_exit(
    mock_request: mock.Mock, mock_error: mock.Mock, status_code: int
):
    mock_request.return_value = _mock_response(status_code, json_data={"error": {"message": "bad request"}})

    with pytest.raises(typer.Exit):
        make_request("PATCH", URL, TOKEN, err_msg="Unable to update Widget.")

    assert mock_error.call_args == mock.call("Unable to update Widget. bad request")


@pytest.mark.parametrize("status_code", [400, 401, 403])
@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_client_error_detail_status_raises_exit(
    mock_request: mock.Mock, mock_error: mock.Mock, status_code: int
):
    mock_request.return_value = _mock_response(status_code, json_data={"detail": "bad request"})

    with pytest.raises(typer.Exit):
        make_request("PATCH", URL, TOKEN, err_msg="Unable to update Widget.")

    assert mock_error.call_args == mock.call("Unable to update Widget. bad request")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_client_error_with_non_json_body_uses_response_text(
    mock_request: mock.Mock, mock_error: mock.Mock
):
    response = _mock_response(400)
    response.json.side_effect = JSONDecodeError("msg", "doc", 0)
    response.text = "plain text error"
    mock_request.return_value = response

    with pytest.raises(typer.Exit):
        make_request("PATCH", URL, TOKEN, err_msg="Unable to update Widget.")

    assert mock_error.call_args == mock.call("Unable to update Widget. plain text error")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_http_error_raises_exit_by_default(mock_request: mock.Mock, mock_error: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_request.return_value = _mock_response(500, raises=error)

    with pytest.raises(typer.Exit):
        make_request("PATCH", URL, TOKEN)

    assert mock_error.call_args == mock.call("HTTP Exception")


@mock.patch("deepfellow.common.rest.httpx.request")
def test_make_request_http_error_reraises_when_reraise_true(mock_request: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    mock_request.return_value = _mock_response(500, raises=error)

    with pytest.raises(httpx.HTTPStatusError):
        make_request("PATCH", URL, TOKEN, reraise=True)


@mock.patch("deepfellow.common.rest.httpx.get")
def test_check_health_returns_none_on_200(mock_get: mock.Mock):
    mock_get.return_value = _mock_response(200)

    check_health("http://example.com")

    assert mock_get.call_args == mock.call("http://example.com/health")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_check_health_non_200_raises_exit_with_http_exception_message(mock_get: mock.Mock, mock_error: mock.Mock):
    error = httpx.HTTPStatusError("server error", request=mock.Mock(), response=mock.Mock())
    response = _mock_response(500, raises=error)
    response.text = "internal error"
    mock_get.return_value = response

    with pytest.raises(typer.Exit):
        check_health("http://example.com")

    assert mock_error.call_args == mock.call("HTTP Exception")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_check_health_connection_refused_raises_exit_with_server_off_message(
    mock_get: mock.Mock, mock_error: mock.Mock
):
    mock_get.side_effect = httpx.ConnectError("Connection refused")

    with pytest.raises(typer.Exit):
        check_health("http://example.com")

    assert mock_error.call_args == mock.call("Deepfellow Server is OFF.")


@mock.patch("deepfellow.common.rest.echo.error")
@mock.patch("deepfellow.common.rest.httpx.get")
def test_check_health_unknown_exception_raises_exit_with_unknown_error_message(
    mock_get: mock.Mock, mock_error: mock.Mock
):
    mock_get.side_effect = ValueError("boom")

    with pytest.raises(typer.Exit):
        check_health("http://example.com")

    assert mock_error.call_args == mock.call("Unknown error when requesting http://example.com/health/health")
