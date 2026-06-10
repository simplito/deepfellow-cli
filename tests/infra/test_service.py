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

import httpx
import pytest
import typer

from deepfellow.infra.service.install import install
from deepfellow.infra.service.uninstall import uninstall


@pytest.fixture(name="name")
def name_fixture() -> str:
    return "name"


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_connection_error(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
    name: str,
) -> None:
    mock_post.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        install(name=name, spec=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_success_without_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
    name: str,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name=name, service_api_key=None, spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_success_with_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
    name: str,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name=name, service_api_key="sk-test-123", spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_with_valid_spec(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
    name: str,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name=name, spec='{"url": "http://host:11434"}')

    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        mock.ANY, mock.ANY, item_name="Service", data={"spec": {"url": "http://host:11434"}}, reraise=True
    )


def test_install_with_invalid_json_spec(name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec="not-json")


@mock.patch("deepfellow.infra.service.install.echo")
def test_install_with_non_object_json_spec(mock_echo: Mock, name: str) -> None:
    with pytest.raises(typer.Exit):
        install(name=name, spec='["a", "b"]')

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--spec must be a JSON object, not an array or scalar.")


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_claude_with_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name="claude", service_api_key="sk-test-123", spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "sk-test-123", "anthropic_version": "2023-06-01"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_google_with_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name="google", service_api_key="google-key-123", spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "google-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_openai_with_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name="openai", service_api_key="openai-key-123", spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "openai-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.install.echo")
@mock.patch("deepfellow.infra.service.install.post")
@mock.patch("deepfellow.infra.service.install.cast")
@mock.patch("deepfellow.infra.service.install.read_env_file")
@mock.patch("deepfellow.infra.service.install.env_set")
def test_install_sindri_with_api_key(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_post: Mock,
    mock_echo: Mock,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(name="sindri", service_api_key="sindri-key-123", spec=None)

    assert mock_post.call_count == 1
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["data"] == {"spec": {"api_key": "sindri-key-123"}}
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.service.uninstall.echo")
@mock.patch("deepfellow.infra.service.uninstall.make_request")
@mock.patch("deepfellow.infra.service.uninstall.cast")
@mock.patch("deepfellow.infra.service.uninstall.read_env_file")
@mock.patch("deepfellow.infra.service.uninstall.env_set")
def test_uninstall_connection_error(
    mock_env_set: Mock,
    mock_read_env_file: Mock,
    mock_cast: Mock,
    mock_make_request: Mock,
    mock_echo: Mock,
    name: str,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(typer.Exit):
        uninstall(name=name)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )
