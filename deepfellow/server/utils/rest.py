"""REST utils."""

from json import JSONDecodeError
from typing import Any

import click
import httpx
import typer

from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.validation import validate_server


def get_server_url(server: str | None) -> str:
    """Return server URL. Repeat until a valid URL is provided."""
    ctx = click.get_current_context()
    config_file = ctx.obj.get("cli-config-file")

    config_server = ctx.obj.get("cli-config").get("df_server_url")
    if server is None and config_server:
        server = config_server

    while server is None:
        try:
            server = echo.prompt("Provide DeepFellow Server address", validation=validate_server)
        except typer.BadParameter:
            echo.error("Invalid Deepfellow Server address. Please try again.")

    if config_server is None or (
        server != config_server and echo.confirm(f"Do you want to set {server} as your default DeepFellow Server?")
    ):
        env_set(config_file, "SERVER_URL", server, should_raise=False, docker_note=False)
        config_server = server

    return server


def get(url: str, token: str, headers: dict[str, str] | None = None, item_name: str | None = None) -> dict[str, Any]:
    """Perform GET on url."""
    echo.debug(f"GET {url}")
    headers = headers or {}
    item_name = item_name or "Item"
    try:
        response = httpx.get(url, headers=headers | {"Authorization": f"Bearer {token}"})
        if response.status_code in (404, 422):  # 422 might happen if user provides non UUID id
            echo.error(f"{item_name} not found.")
            raise typer.Exit(1)

        if response.status_code == 403:
            try:
                data = response.json()
                message = data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to get {item_name}. {message}.")
            raise typer.Exit(1)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    return response.json()


def delete(url: str, token: str, headers: dict[str, str] | None = None, item_name: str | None = None) -> None:
    """Perform DELETE on url."""
    echo.debug(f"DELETE {url}")
    headers = headers or {}
    item_name = item_name or "Item"
    try:
        response = httpx.delete(url, headers=headers | {"Authorization": f"Bearer {token}"})

        if response.status_code in (404, 422):  # 422 might happen if user provides non UUID id
            echo.error(f"{item_name} not found.")
            raise typer.Exit(1)

        if response.status_code == 403:
            try:
                data = response.json()
                message = data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to delete the {item_name}. {message}.")
            raise typer.Exit(1)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc


def post(
    url: str,
    token: str,
    headers: dict[str, str] | None = None,
    item_name: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST request on url using data."""
    echo.debug(f"POST {url} {data=}")
    headers = headers or {}
    item_name = item_name or "Item"
    data = data or {}
    try:
        response = httpx.post(
            url,
            headers=headers | {"Authorization": f"Bearer {token}"},
            json=data,
        )

        if response.status_code in (401, 403):
            try:
                response_data = response.json()
                message = response_data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to create {item_name}. {message}.")
            raise typer.Exit(1)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    return response.json()
