"""Utils for the project api-key requests."""

from dataclasses import dataclass
from typing import Any, Literal

from deepfellow.common.rest import delete, get, post
from deepfellow.server.utils.time import datetime_to_str


@dataclass
class ApiKey:
    id: str
    object: Literal["organization.project.api_key"]
    name: str
    redacted_value: str
    created_at: float
    last_used_at: float
    value: str | None

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "ApiKey":
        """Instantiate from data."""
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
        }
        if self.value is not None:
            data["value"] = self.value

        return data

    def __str__(self) -> str:
        """String represantation of the ApiKey."""
        return "\n".join(f"{key}: {value}" for key, value in self.as_dict().items())


def get_api_key(server: str | None, token: str, organization_id: str, project_id: str, api_key_id: str) -> ApiKey:
    """Get the project using DELETE."""
    data = get(
        f"{server}/v1/organization/projects/{project_id}/api_keys/{api_key_id}",
        token,
        item_name="Project API Key",
        headers={"OpenAI-Organization": organization_id},
    )
    return ApiKey.from_data(data)


def delete_api_key(server: str | None, token: str, organization_id: str, project_id: str, api_key_id: str) -> None:
    """Delete the project using DELETE."""
    delete(
        f"{server}/v1/organization/projects/{project_id}/api_keys/{api_key_id}",
        token,
        item_name="Project API Key",
        headers={"OpenAI-Organization": organization_id},
    )


def create_api_key(server: str | None, token: str, organization_id: str, project_id: str, name: str) -> ApiKey:
    """Create project api key."""
    data = post(
        f"{server}/v1/organization/projects/{project_id}/api_keys",
        token,
        item_name="Project ApiKey",
        data={"name": name},
        headers={"OpenAI-Organization": organization_id},
    )
    return ApiKey(**data)
