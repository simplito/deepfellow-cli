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

import httpx

from deepfellow.common.state import state
from deepfellow.server.utils.login import get_token, get_token_from_login, try_refresh_token

SERVER = "http://localhost:8000"

LOGIN_RESPONSE = {
    "access_token": "dfuser_abc",
    "refresh_token": "dfuserrefresh_xyz",
    "access_expires_at": 9999999999,
    "refresh_expires_at": 9999999999,
}

REFRESH_RESPONSE = {
    "access_token": "dfuser_new",
    "refresh_token": "dfuserrefresh_new",
    "access_expires_at": 9999999999,
    "refresh_expires_at": 9999999999,
}

# ── get_token_from_login ──────────────────────────────────────────────────────


@mock.patch("deepfellow.server.utils.login.save_env_file")
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={})
@mock.patch("deepfellow.server.utils.login.httpx.post")
@mock.patch("deepfellow.server.utils.login.echo.prompt_until_valid", side_effect=["user@example.com", "password123"])
def test_get_token_from_login_writes_token_key(
    mock_prompt: mock.Mock,
    mock_post: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = LOGIN_RESPONSE
    mock_post.return_value = mock_response

    token = get_token_from_login(secrets_file, SERVER)

    assert token == "dfuser_abc"
    saved_secrets = mock_save.call_args[0][1]
    assert saved_secrets["DF_USER_TOKEN"] == "dfuser_abc"
    assert saved_secrets["DF_USER_REFRESH_TOKEN"] == "dfuserrefresh_xyz"


@mock.patch("deepfellow.server.utils.login.save_env_file")
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={})
@mock.patch("deepfellow.server.utils.login.httpx.post")
@mock.patch("deepfellow.server.utils.login.echo.prompt_until_valid", side_effect=["user@example.com", "password123"])
def test_get_token_from_login_no_refresh_token_in_response(
    mock_prompt: mock.Mock,
    mock_post: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "dfuser_abc", "token_type": "bearer", "expires_at": 9999999999}
    mock_post.return_value = mock_response

    token = get_token_from_login(secrets_file, SERVER)

    assert token == "dfuser_abc"
    saved_secrets = mock_save.call_args[0][1]
    assert saved_secrets["DF_USER_TOKEN"] == "dfuser_abc"
    assert "DF_USER_REFRESH_TOKEN" not in saved_secrets


# ── try_refresh_token ─────────────────────────────────────────────────────────


@mock.patch("deepfellow.server.utils.login.save_env_file")
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_REFRESH_TOKEN": "dfuserrefresh_xyz"})
@mock.patch("deepfellow.server.utils.login.httpx.post")
def test_try_refresh_token_success_returns_new_token_and_saves(
    mock_post: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = REFRESH_RESPONSE
    mock_post.return_value = mock_response

    result = try_refresh_token(secrets_file, SERVER)

    assert result == "dfuser_new"
    assert mock_save.call_count == 1
    saved_secrets = mock_save.call_args[0][1]
    assert saved_secrets["DF_USER_TOKEN"] == "dfuser_new"
    assert saved_secrets["DF_USER_REFRESH_TOKEN"] == "dfuserrefresh_new"


@mock.patch("deepfellow.server.utils.login.save_env_file")
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_REFRESH_TOKEN": "dfuserrefresh_xyz"})
@mock.patch("deepfellow.server.utils.login.httpx.post")
def test_try_refresh_token_uses_refresh_token_as_bearer(
    mock_post: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = REFRESH_RESPONSE
    mock_post.return_value = mock_response

    try_refresh_token(secrets_file, SERVER)

    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer dfuserrefresh_xyz"
    assert "json" not in call_kwargs


@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_REFRESH_TOKEN": "dfuserrefresh_xyz"})
@mock.patch("deepfellow.server.utils.login.httpx.post")
def test_try_refresh_token_401_returns_none(
    mock_post: mock.Mock,
    mock_read: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 401
    mock_post.return_value = mock_response

    result = try_refresh_token(secrets_file, SERVER)

    assert result is None


@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={})
def test_try_refresh_token_no_stored_refresh_token_returns_none(
    mock_read: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()

    result = try_refresh_token(secrets_file, SERVER)

    assert result is None


# ── get_token ─────────────────────────────────────────────────────────────────


@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_TOKEN": "dfuser_valid"})
@mock.patch("deepfellow.server.utils.login.httpx.get")
def test_get_token_valid_token_returns_without_refresh(
    mock_get: mock.Mock,
    mock_read: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    result = get_token(secrets_file, SERVER)

    assert result == "dfuser_valid"


@mock.patch("deepfellow.server.utils.login.try_refresh_token", return_value="dfuser_new")
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_TOKEN": "dfuser_expired"})
@mock.patch("deepfellow.server.utils.login.httpx.get")
def test_get_token_401_refresh_succeeds(
    mock_get: mock.Mock,
    mock_read: mock.Mock,
    mock_refresh: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    result = get_token(secrets_file, SERVER)

    assert result == "dfuser_new"
    assert mock_refresh.call_count == 1


@mock.patch("deepfellow.server.utils.login.get_token_from_login", return_value="dfuser_fresh")
@mock.patch("deepfellow.server.utils.login.try_refresh_token", return_value=None)
@mock.patch("deepfellow.server.utils.login.read_env_file", return_value={"DF_USER_TOKEN": "dfuser_expired"})
@mock.patch("deepfellow.server.utils.login.httpx.get")
def test_get_token_401_refresh_401_falls_back_to_login(
    mock_get: mock.Mock,
    mock_read: mock.Mock,
    mock_refresh: mock.Mock,
    mock_login: mock.Mock,
    tmp_path: Path,
):
    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    mock_response = mock.Mock()
    mock_response.status_code = 401
    mock_get.return_value = mock_response

    result = get_token(secrets_file, SERVER)

    assert result == "dfuser_fresh"
    assert mock_refresh.call_count == 1
    assert mock_login.call_count == 1


# ── logout ────────────────────────────────────────────────────────────────────


@mock.patch("deepfellow.server.logout.save_env_file")
@mock.patch("deepfellow.server.logout.read_env_file")
@mock.patch("deepfellow.server.logout.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.logout.httpx.post")
@mock.patch("deepfellow.server.logout.get_server_url", return_value=SERVER)
def test_logout_successful_clears_token_key(
    mock_server_url: mock.Mock,
    mock_post: mock.Mock,
    mock_get_token: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    from deepfellow.server.logout import logout

    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file
    mock_read.return_value = {
        "DF_USER_TOKEN": "dfuser_abc",
        "DF_USER_REFRESH_TOKEN": "dfuserrefresh_xyz",
        "OTHER_KEY": "kept",
    }
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    logout()

    saved_secrets = mock_save.call_args[0][1]
    assert "DF_USER_TOKEN" not in saved_secrets
    assert "DF_USER_REFRESH_TOKEN" not in saved_secrets
    assert saved_secrets.get("OTHER_KEY") == "kept"


@mock.patch("deepfellow.server.logout.save_env_file")
@mock.patch("deepfellow.server.logout.read_env_file")
@mock.patch("deepfellow.server.logout.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.logout.httpx.post")
@mock.patch("deepfellow.server.logout.get_server_url", return_value=SERVER)
def test_logout_uses_bearer_auth_no_body(
    mock_server_url: mock.Mock,
    mock_post: mock.Mock,
    mock_get_token: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    from deepfellow.server.logout import logout

    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file
    mock_read.return_value = {"DF_USER_TOKEN": "dfuser_abc"}
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    logout()

    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer dfuser_abc"
    assert "json" not in call_kwargs


@mock.patch("deepfellow.server.logout.save_env_file")
@mock.patch("deepfellow.server.logout.read_env_file")
@mock.patch("deepfellow.server.logout.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.logout.httpx.post")
@mock.patch("deepfellow.server.logout.get_server_url", return_value=SERVER)
def test_logout_clears_locally_even_when_server_call_fails(
    mock_server_url: mock.Mock,
    mock_post: mock.Mock,
    mock_get_token: mock.Mock,
    mock_read: mock.Mock,
    mock_save: mock.Mock,
    tmp_path: Path,
):
    from deepfellow.server.logout import logout

    secrets_file = tmp_path / "secrets"
    secrets_file.touch()
    state.cli_secrets_file = secrets_file
    mock_read.return_value = {"DF_USER_TOKEN": "dfuser_abc"}
    mock_post.side_effect = httpx.ConnectError("connection refused")

    logout()

    assert mock_save.call_count == 1
    saved_secrets = mock_save.call_args[0][1]
    assert "DF_USER_TOKEN" not in saved_secrets
