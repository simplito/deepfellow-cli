# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.


from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import DF_SERVER_IMAGE, DF_SERVER_IMAGE_HUB, DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.server.update import update


@pytest.fixture
def server_values() -> dict:
    return {"df_server_image": "some-image"}


@pytest.fixture
def compose_data() -> dict:
    return {"services": {"server": {}}}


@pytest.fixture
def compose_data_with_pull_policy() -> dict:
    return {"services": {"server": {"pull_policy": "always"}}}


@pytest.fixture
def default_update_kwargs(directory: Path) -> dict:
    return {
        "directory": directory,
        "image": DF_SERVER_IMAGE,
        "local_image": False,
        "tag": None,
    }


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_calls_check_server_directory(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((default_update_kwargs["directory"],), {})


@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_raises_when_tag_and_custom_image_provided(
    mock_check: Mock,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        update(directory=directory, image="custom-image", local_image=False, tag="0.15.0")


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_and_no_pull_policy(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "local_image": True})

    assert compose_data["services"]["server"]["pull_policy"] == "never"
    assert mock_save.call_count == 1
    assert mock_save.call_args == (
        (compose_data, default_update_kwargs["directory"] / DOCKER_COMPOSE_CONFIG_FILENAME),
        {},
    )


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_and_pull_policy(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data_with_pull_policy: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data_with_pull_policy
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "local_image": True})

    assert compose_data_with_pull_policy["services"]["server"]["pull_policy"] == "always"
    assert mock_save.call_count == 0


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_no_local_image_and_pull_policy(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data_with_pull_policy: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data_with_pull_policy
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert "pull_policy" not in compose_data_with_pull_policy["services"]["server"]
    assert mock_save.call_count == 1
    assert mock_save.call_args == (
        (compose_data_with_pull_policy, default_update_kwargs["directory"] / DOCKER_COMPOSE_CONFIG_FILENAME),
        {},
    )


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_no_image_no_pull_policy(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_save.call_count == 0


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_with_tag(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == (
        (mock.ANY, "SERVER_IMAGE", f"{DF_SERVER_IMAGE_HUB}:0.15.0"),
        {"quiet": False, "docker_note": False},
    )


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_calls_env_set_when_env_image_differs_from_provided(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_newest: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = DF_SERVER_IMAGE

    update(**default_update_kwargs)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == (
        (mock.ANY, "SERVER_IMAGE", DF_SERVER_IMAGE),
        {"quiet": False, "docker_note": False},
    )


@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_with_custom_image_and_no_tag_uses_image_as_is(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_newest: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "image": "custom-image"})

    assert mock_newest.call_count == 0
    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == (
        (mock.ANY, "SERVER_IMAGE", "custom-image"),
        {"quiet": False, "docker_note": False},
    )


@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_call_env_set_when_image_unchanged(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_newest: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_server_image": DF_SERVER_IMAGE}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = DF_SERVER_IMAGE

    update(**default_update_kwargs)

    assert mock_env_set.call_count == 0


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_restarts_when_confirmed(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True

    update(**default_update_kwargs)

    assert mock_stop.call_count == 1
    assert mock_stop.call_args == ((default_update_kwargs["directory"],), {})
    assert mock_start.call_count == 1
    assert mock_start.call_args == ((default_update_kwargs["directory"],), {})


@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_restart_when_not_confirmed(
    mock_check: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
