from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.install import assert_docker


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
def test_assert_docker_installed(mock_is_docker_installed: Mock, mock_echo: Mock) -> None:
    mock_is_docker_installed.return_value = True

    assert_docker()

    assert mock_echo.error.call_count == 0


@mock.patch("deepfellow.common.install.echo")
@mock.patch("deepfellow.common.install.is_docker_installed")
def test_assert_docker_not_installed(mock_is_docker_installed: Mock, mock_echo: Mock) -> None:
    mock_is_docker_installed.return_value = False

    with pytest.raises(typer.Exit):
        assert_docker()

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Missing docker. Install docker.")
