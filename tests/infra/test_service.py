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

import click
import httpx
import pytest

from deepfellow.infra.service.install import install
from deepfellow.infra.service.uninstall import uninstall


@pytest.fixture(name="name")
def name_fixture() -> str:
    return "name"


@pytest.fixture(name="ctx")
def ctx_fixture() -> Mock:
    return Mock()


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
    ctx: Mock,
    name: str,
) -> None:
    mock_post.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(click.exceptions.Exit):
        install(ctx=ctx, name=name, spec=None)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


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
    ctx: Mock,
    name: str,
) -> None:
    mock_post.return_value = {"status": "OK"}

    install(ctx=ctx, name=name, spec='{"url": "http://host:11434"}')

    assert mock_post.call_count == 1
    assert mock_post.call_args == mock.call(
        mock.ANY, mock.ANY, item_name="Service", data={"spec": {"url": "http://host:11434"}}, reraise=True
    )


def test_install_with_invalid_json_spec(ctx: Mock, name: str) -> None:
    with pytest.raises(click.exceptions.Exit):
        install(ctx=ctx, name=name, spec="not-json")


@mock.patch("deepfellow.infra.service.install.echo")
def test_install_with_non_object_json_spec(mock_echo: Mock, ctx: Mock, name: str) -> None:
    with pytest.raises(click.exceptions.Exit):
        install(ctx=ctx, name=name, spec='["a", "b"]')

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--spec must be a JSON object, not an array or scalar.")


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
    ctx: Mock,
    name: str,
) -> None:
    mock_make_request.side_effect = httpx.ConnectError("TEST")

    with pytest.raises(click.exceptions.Exit):
        uninstall(ctx=ctx, name=name)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )
