# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
from unittest import mock
from unittest.mock import Mock

from deepfellow.server.project.api_key.utils import ApiKey, create_api_key, delete_api_key, get_api_key


def api_key_data() -> dict[str, Any]:
    return {
        "id": "key-id",
        "object": "organization.project.api_key",
        "name": "Key Name",
        "redacted_value": "sk-...abcd",
        "created_at": 0.0,
        "last_used_at": 0.0,
        "value": None,
    }


def test_from_data_defaults_value_to_none_when_missing():
    data = api_key_data()
    del data["value"]

    api_key = ApiKey.from_data(data)

    assert api_key.value is None


def test_from_data_keeps_value_when_present():
    data = api_key_data()
    data["value"] = "sk-secret"

    api_key = ApiKey.from_data(data)

    assert api_key.value == "sk-secret"


@mock.patch("deepfellow.server.project.api_key.utils.datetime_to_str")
def test_created_at_to_str_returns_formatted_date(mock_datetime_to_str: Mock):
    mock_datetime_to_str.return_value = "2026-07-31"
    api_key = ApiKey.from_data(api_key_data())

    result: str = api_key.created_at_to_str()

    assert result == "2026-07-31"
    assert mock_datetime_to_str.call_count == 1
    assert mock_datetime_to_str.call_args == mock.call(api_key.created_at)


@mock.patch("deepfellow.server.project.api_key.utils.datetime_to_str")
def test_last_used_at_to_str_returns_formatted_date(mock_datetime_to_str: Mock):
    mock_datetime_to_str.return_value = "2026-07-30"
    api_key = ApiKey.from_data(api_key_data())

    result: str = api_key.last_used_at_to_str()

    assert result == "2026-07-30"
    assert mock_datetime_to_str.call_count == 1
    assert mock_datetime_to_str.call_args == mock.call(api_key.last_used_at)


def test_as_dict_excludes_value_when_none() -> None:
    api_key = ApiKey.from_data(api_key_data())

    result: dict[str, str] = api_key.as_dict()

    assert "value" not in result
    assert result["name"] == "Key Name"
    assert result["id"] == "key-id"


def test_as_dict_includes_value_when_present() -> None:
    data = api_key_data()
    data["value"] = "sk-secret"
    api_key = ApiKey.from_data(data)

    result: dict[str, str] = api_key.as_dict()

    assert result["value"] == "sk-secret"


def test_str_joins_as_dict_items_as_lines() -> None:
    api_key = ApiKey.from_data(api_key_data())

    result: str = str(api_key)

    for key, value in api_key.as_dict().items():
        assert f"{key}: {value}" in result.splitlines()


@mock.patch("deepfellow.server.project.api_key.utils.get")
def test_get_api_key_returns_api_key(mock_get: Mock):
    mock_get.return_value = api_key_data()

    result: ApiKey = get_api_key("https://server", "token", "org-id", "project-id", "key-id")

    assert isinstance(result, ApiKey)
    assert result.id == "key-id"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(
        "https://server/v1/organization/projects/project-id/api_keys/key-id",
        "token",
        item_name="Project API Key",
        headers={"OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.project.api_key.utils.delete")
def test_delete_api_key_calls_delete(mock_delete: Mock):
    delete_api_key("https://server", "token", "org-id", "project-id", "key-id")

    assert mock_delete.call_count == 1
    assert mock_delete.call_args == mock.call(
        "https://server/v1/organization/projects/project-id/api_keys/key-id",
        "token",
        item_name="Project API Key",
        headers={"OpenAI-Organization": "org-id"},
    )


@mock.patch("deepfellow.server.project.api_key.utils.post")
def test_create_api_key_returns_api_key(mock_post: Mock):
    mock_post.return_value = api_key_data()

    result: ApiKey = create_api_key("https://server", "token", "org-id", "project-id", "Key Name")

    assert isinstance(result, ApiKey)
    assert result.name == "Key Name"
    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        "https://server/v1/organization/projects/project-id/api_keys",
        "token",
        item_name="Project ApiKey",
        data={"name": "Key Name"},
        headers={"OpenAI-Organization": "org-id"},
    )
