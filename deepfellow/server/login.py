"""Login command."""

from pathlib import Path
from typing import cast

import httpx
import typer

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_email, validate_url
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def login(
    directory: Path = directory_option("Target directory for the DFServer installation."),
    server: str | None = typer.Option(None, callback=validate_url, help="DeepFellow server address"),
    email: str | None = typer.Option(None, callback=validate_email, help="User email"),
) -> str:
    """Login user and return the token.

    Raises:
        typer.Exit if invalid credentials.
    """
    # Get user's email and password
    if email is None:
        email_collected = False
        while email_collected is False:
            try:
                email = echo.prompt("Provide your email", validation=validate_email)
                email_collected = True
            except typer.BadParameter:
                echo.error("Invalid email. Please try again.")

    password = echo.prompt("Provide your password", password=True)

    # Get server URL
    if server is None:
        server_collected = False
        while server_collected is False:
            try:
                server = echo.prompt("Provide DF Server address", validation=validate_url)
                server_collected = True
            except typer.BadParameter:
                echo.error("Invalid server address. Please try again.")

    # Authorize the user (we need the server's URL)
    server = cast("str", server)
    server.rstrip("/")
    url = f"{server}/auth/login"
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

    # Store token in `directory/.secret`
    secrets_file = directory / ".secret"
    secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
    secrets["DF_USER_TOKEN"] = token
    secrets["DF_USER_TOKEN_EXPIRY"] = data["expired_at"]

    save_env_file(secrets_file, secrets, docker_note=False)

    # Return token to pipe
    return token
