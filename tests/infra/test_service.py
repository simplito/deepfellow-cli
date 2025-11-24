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
        install(ctx=ctx, name=name)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "No connection with DeepFellow Infra. Is it up? (deepfellow infra start)"
    )


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
