"""Utils for the organization requests."""

from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError

import httpx
import typer
from tzlocal import get_localzone

from deepfellow.common.echo import echo


@dataclass
class Organization:
    id: str
    created_at: float
    name: str
    owner_id: str

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return str(datetime.fromtimestamp(self.created_at, tz=get_localzone()))

    def as_dict(self) -> dict[str, str]:
        """Dictionary representation of Organization."""
        return {
            "name": self.name,
            "id": self.id,
            "created_at": self.created_at_to_str(),
            "owner_id": self.owner_id,
        }

    def __str__(self) -> str:
        """String represantation of the Organization."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def get_organization(server: str | None, organization_id: str, token: str) -> Organization:
    """Return the organization dict."""
    url = f"{server}/v1/organization/{organization_id}"
    echo.debug(f"GET {url}")
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code in (404, 422):  # 422 might happen if user provides non UUID id
            echo.error("Organization not found.")
            raise typer.Exit(1)

        if response.status_code == 403:
            try:
                data = response.json()
                message = data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to get the organization. {message}.")
            raise typer.Exit(1)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    data = response.json()
    return Organization(**data["organization"])


def delete_organization(server: str | None, organization_id: str, token: str) -> None:
    """Delete the organization using DELETE."""
    url = f"{server}/v1/organization/{organization_id}"
    echo.debug(f"DELETE {url}")
    try:
        response = httpx.delete(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )

        if response.status_code in (404, 422):  # 422 might happen if user provides non UUID id
            echo.error("Organization not found.")
            raise typer.Exit(1)

        if response.status_code == 403:
            try:
                data = response.json()
                message = data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to delete the organization. {message}.")
            raise typer.Exit(1)

        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc


def list_organizations(server: str | None, token: str) -> list[Organization]:
    """List organizations."""
    url = f"{server}/v1/organization/"
    echo.debug(f"GET {url}")
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    # Response
    data = response.json()
    return [Organization(**org) for org in data["data"]]


def create_organization(server: str | None, token: str, name: str) -> Organization:
    """Create organization."""
    url = f"{server}/v1/organization/"
    data = {"name": name}
    echo.debug(f"POST {url} {data=}")
    try:
        response = httpx.post(
            f"{server}/v1/organization/",
            headers={"Authorization": f"Bearer {token}"},
            json=data,
        )

        if response.status_code in (401, 403):
            try:
                data = response.json()
                message = data["detail"]
            except JSONDecodeError:
                message = response.text

            echo.error(f"Unable to create the organization. {message}.")
            raise typer.Exit(1)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        echo.error("HTTP Exception")
        echo.debug(exc)
        raise typer.Exit(1) from exc

    # Response
    data = response.json()
    return Organization(**data["organization"])
