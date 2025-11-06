"""Utils for the organization api-key requests."""

from dataclasses import dataclass
from typing import Any, Literal

from deepfellow.common.rest import delete, get, post
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class Owner:
    created_at: float
    id: str
    name: str
    object: Literal["organization.user"]
    role: str
    type: Literal["user"]


@dataclass
class ApiKey:
    id: str
    object: Literal["organization.admin_api_key"]
    name: str
    redacted_value: str
    owner: Owner
    created_at: float
    last_used_at: float
    value: str | None

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ApiKey":
        """Instantiate from data."""
        data["owner"] = Owner(**data["owner"])
        if data.get("value") is None:
            data["value"] = None

        return cls(**data)

    def created_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.created_at)

    def last_used_at_to_str(self) -> str:
        """Convert created_at to a localized date string."""
        return datetime_to_str(self.last_used_at)

    def as_dict(self) -> dict[str, str]:
        """Dictionary representation of ApiKey."""
        data = {
            "name": self.name,
            "redacted_value": self.redacted_value,
            "id": self.id,
            "created_at": self.created_at_to_str(),
            "last_used_at": self.last_used_at_to_str(),
            "owner-name": self.owner.name,
            "owner-id": self.owner.id,
        }
        if self.value is not None:
            data["value"] = self.value

        return data

    def __str__(self) -> str:
        """String represantation of the ApiKey."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def get_admin_api_key(server: str | None, token: str, organization_id: str, admin_api_key_id: str) -> ApiKey:
    """Get the organization using DELETE."""
    data = get(
        f"{server}/v1/organization/admin_api_keys/{admin_api_key_id}",
        token,
        item_name="Organization API Key",
        headers={"OpenAI-Organization": organization_id},
    )
    return ApiKey.from_data(data)


def delete_admin_api_key(server: str | None, token: str, organization_id: str, admin_api_key_id: str) -> None:
    """Delete the organization API Keyusing DELETE."""
    delete(
        f"{server}/v1/organization/admin_api_keys/{admin_api_key_id}",
        token,
        item_name="Organization API Key",
        headers={"OpenAI-Organization": organization_id},
    )


def create_admin_api_key(server: str | None, token: str, organization_id: str, name: str) -> ApiKey:
    """Create organization API Key."""
    data = post(
        f"{server}/v1/organization/admin_api_keys",
        token,
        item_name="Organization API Key",
        data={"name": name},
        headers={"OpenAI-Organization": organization_id},
    )
    return ApiKey.from_data(data)
