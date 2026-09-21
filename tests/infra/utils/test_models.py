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
import typer

from deepfellow.infra.utils.models import get_service_models


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_get_service_models_returns_list_on_success(mock_make_request: Mock, mock_env_set: Mock) -> None:
    mock_make_request.return_value = {"list": [{"id": "llama-3.1-8B", "type": "ollama", "installed": True}]}

    result = get_service_models("http://infra:8086", "test-key", "ollama")

    assert result == [{"id": "llama-3.1-8B", "type": "ollama", "installed": True}]


@mock.patch("deepfellow.infra.utils.models.echo")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_get_service_models_raises_when_list_field_is_missing(
    mock_make_request: Mock, mock_env_set: Mock, mock_echo: Mock
) -> None:
    mock_make_request.return_value = {"unexpected": "shape"}

    with pytest.raises(typer.Exit):
        get_service_models("http://infra:8086", "test-key", "ollama")

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.infra.utils.models.echo")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_get_service_models_raises_when_item_is_not_a_dict(
    mock_make_request: Mock, mock_env_set: Mock, mock_echo: Mock
) -> None:
    mock_make_request.return_value = {"list": ["not-a-dict"]}

    with pytest.raises(typer.Exit):
        get_service_models("http://infra:8086", "test-key", "ollama")

    assert mock_echo.error.call_count == 1


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param({"type": "ollama", "installed": True}, id="missing_id"),
        pytest.param({"id": "llama-3.1-8B", "installed": True}, id="missing_type"),
        pytest.param({"id": "llama-3.1-8B", "type": "ollama"}, id="missing_installed"),
        pytest.param({"id": 123, "type": "ollama", "installed": True}, id="id_not_a_string"),
        pytest.param({"id": "llama-3.1-8B", "type": 123, "installed": True}, id="type_not_a_string"),
    ],
)
@mock.patch("deepfellow.infra.utils.models.echo")
@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_get_service_models_raises_when_entry_is_missing_an_expected_field(
    mock_make_request: Mock,
    mock_env_set: Mock,
    mock_echo: Mock,
    entry: dict[str, object],
) -> None:
    mock_make_request.return_value = {"list": [entry]}

    with pytest.raises(typer.Exit):
        get_service_models("http://infra:8086", "test-key", "ollama")

    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.env_set")
@mock.patch("deepfellow.infra.utils.models.make_request")
def test_get_service_models_forwards_installed_filter_and_err_msg(mock_make_request: Mock, mock_env_set: Mock) -> None:
    mock_make_request.return_value = {"list": []}

    get_service_models("http://infra:8086", "test-key", "ollama", installed=True, err_msg="Custom error.")

    assert mock_make_request.call_args == mock.call(
        method="GET",
        url="http://infra:8086/admin/services/ollama/models?installed=true",
        token="test-key",
        err_msg="Custom error.",
        reraise=True,
    )
