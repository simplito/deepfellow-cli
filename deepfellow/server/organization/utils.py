"""Utils for the organization requests."""

from dataclasses import dataclass

from deepfellow.common.echo import echo
from deepfellow.server.utils.rest import get, post
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class Organization:
    id: str
    created_at: float
    name: str
    owner_id: str

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.created_at)

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
    data = get(f"{server}/v1/organization/{organization_id}", token, item_name="Organization")
    return Organization(**data["organization"])


def delete_organization(server: str | None, organization_id: str, _token: str) -> None:
    """Delete the organization using DELETE."""
    raise NotImplementedError("Organization can't be deleted")
    url = f"{server}/v1/organization/{organization_id}"
    echo.debug(f"DELETE {url}")


def list_organizations(server: str | None, token: str) -> list[Organization]:
    """List organizations."""
    data = get(f"{server}/v1/organization/", token, item_name="Organizations")
    return [Organization(**org) for org in data["data"]]


def create_organization(server: str | None, token: str, name: str) -> Organization:
    """Create organization."""
    url = f"{server}/v1/organization/"
    data = post(url, token, item_name="Organization", data={"name": name})
    return Organization(**data["organization"])
