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

import pytest

from deepfellow.server.organization.utils import (
    Organization,
    create_organization,
    delete_organization,
    get_organization,
    list_organizations,
)


@pytest.fixture
def organization() -> Organization:
    return Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")


@mock.patch("deepfellow.server.organization.utils.datetime_to_str")
def test_created_at_to_str_returns_localized_string(mock_datetime_to_str: Mock, organization: Organization) -> None:
    mock_datetime_to_str.return_value = "2026-07-31 12:00:00"

    result: str = organization.created_at_to_str()

    assert result == "2026-07-31 12:00:00"
    assert mock_datetime_to_str.call_args == mock.call(0.0)


@mock.patch("deepfellow.server.organization.utils.datetime_to_str")
def test_as_dict_returns_expected_keys(mock_datetime_to_str: Mock, organization: Organization) -> None:
    mock_datetime_to_str.return_value = "2026-07-31 12:00:00"

    result: dict[str, str] = organization.as_dict()

    assert result == {
        "name": "Acme",
        "id": "org-id",
        "created_at": "2026-07-31 12:00:00",
        "owner_id": "owner-id",
    }


@mock.patch("deepfellow.server.organization.utils.datetime_to_str")
def test_str_joins_dict_items_with_newlines(mock_datetime_to_str: Mock, organization: Organization) -> None:
    mock_datetime_to_str.return_value = "2026-07-31 12:00:00"

    result: str = str(organization)

    assert result == "name: Acme\nid: org-id\ncreated_at: 2026-07-31 12:00:00\nowner_id: owner-id"


@mock.patch("deepfellow.server.organization.utils.get")
def test_get_organization_returns_organization(mock_get: Mock) -> None:
    mock_get.return_value = {
        "organization": {"id": "org-id", "created_at": 0.0, "name": "Acme", "owner_id": "owner-id"}
    }

    result: Organization = get_organization("https://server", "org-id", "token")

    assert result == Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/admin/organization/org-id", "token", item_name="Organization"
    )


def test_delete_organization_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        delete_organization("https://server", "org-id", "token")


@mock.patch("deepfellow.server.organization.utils.get")
def test_list_organizations_returns_organizations(mock_get: Mock) -> None:
    mock_get.return_value = {
        "data": [
            {"id": "org-1", "created_at": 0.0, "name": "Acme", "owner_id": "owner-1"},
            {"id": "org-2", "created_at": 1.0, "name": "Globex", "owner_id": "owner-2"},
        ]
    }

    result: list[Organization] = list_organizations("https://server", "token")

    assert result == [
        Organization(id="org-1", created_at=0.0, name="Acme", owner_id="owner-1"),
        Organization(id="org-2", created_at=1.0, name="Globex", owner_id="owner-2"),
    ]
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call("https://server/admin/organization/", "token", item_name="Organizations")


@mock.patch("deepfellow.server.organization.utils.post")
def test_create_organization_returns_organization(mock_post: Mock) -> None:
    mock_post.return_value = {
        "organization": {"id": "org-id", "created_at": 0.0, "name": "Acme", "owner_id": "owner-id"}
    }

    result: Organization = create_organization("https://server", "token", "Acme")

    assert result == Organization(id="org-id", created_at=0.0, name="Acme", owner_id="owner-id")
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/admin/organization/", "token", item_name="Organization", data={"name": "Acme"}
    )
