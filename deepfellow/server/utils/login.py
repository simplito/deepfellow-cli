# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Login util."""

from pathlib import Path

import httpx
import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_email, validate_password


def get_token(secrets_file: Path, server: str) -> str:
    """Load token from the secrets file.

    Fallback to refresh_token if access token is expired, then to get_token_from_login.

    Args:
        secrets_file (Path): DeepFellow Server secrets
        server (str): DeepFellow Server URL

    Returns:
        Valid token string

    Raises:
        typer.Exit for HTTPError other than 401
    """
    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    token = secrets.get("DF_USER_TOKEN")
    if token is None:
        echo.debug("Token not found in secrets file or it does not exist. Falling back to login.")
        return get_token_from_login(secrets_file, server)

    # Authenticate to check if user is able to log in.
    url = f"{server}/auth/me"
    echo.debug(f"GET {url}")
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            echo.debug("Retrieved token is not valid. Attempting token refresh.")
            new_token = try_refresh_token(secrets_file, server)
            if new_token is not None:
                echo.debug("Token refreshed successfully.")
                return new_token

            echo.error("Token refresh failed. Falling back to login.")
            return get_token_from_login(secrets_file, server)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    return token


def try_refresh_token(secrets_file: Path, server: str) -> str | None:
    """Attempt to obtain a new access token using the stored refresh token against /auth/refresh.

    Args:
        secrets_file (Path): DeepFellow Server secrets
        server (str): DeepFellow Server URL

    Returns:
        New access token string on success, None if refresh is not possible or fails
    """
    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    refresh_token = secrets.get("DF_USER_REFRESH_TOKEN")
    if refresh_token is None:
        return None

    url = f"{server}/auth/refresh"
    echo.debug(f"POST {url}")
    try:
        response = httpx.post(url, headers={"Authorization": f"Bearer {refresh_token}"}, timeout=10.0)
        if response.status_code == 401:
            return None

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.debug(exc)
        return None

    data = response.json()
    new_token = data["access_token"]
    secrets["DF_USER_TOKEN"] = new_token
    secrets["DF_USER_REFRESH_TOKEN"] = data["refresh_token"]
    save_env_file(secrets_file, secrets, docker_note=False, quiet=True)
    return new_token


def get_token_from_login(secrets_file: Path, server: str, email: str | None = None, password: str | None = None) -> str:
    """Login User and return the config.

    Args:
        secrets_file (Path): DeepFellow Server secrets
        server (str): DeepFellow Server URL
        email (str): User email
        password (str): User password

    Returns:
        token string

    Raises:
        typer.Exit for bad credentials or HTTPError
    """
    # Get user's email and password
    email = email or echo.prompt_until_valid("Provide your email", validate_email)
    password = password or echo.prompt_until_valid("Provide your password", validate_password, password=True)

    # Authorize the user (we need the server's URL)
    url = f"{server}/auth/login"
    echo.debug(f"POST {url}")
    try:
        response = httpx.post(url, json={"email": email, "password": password}, timeout=10.0)
        if response.status_code == 401:
            echo.error("Not authorized. Invalid credentials.")
            raise typer.Exit(1)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    if response.status_code != 200:
        echo.error("Unknown error")
        raise typer.Exit(1)

    data = response.json()
    token = data["access_token"]

    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    secrets["DF_USER_TOKEN"] = token
    secrets["DF_USER_REFRESH_TOKEN"] = data["refresh_token"]

    save_env_file(secrets_file, secrets, docker_note=False)

    return token
