# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import (
    DF_SERVER_IMAGE,
    DF_SERVER_IMAGE_HUB,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_RABBITMQ,
)
from deepfellow.server.update import update
from deepfellow.server.utils.configure import NightshiftConfig


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
def nightshift_config() -> NightshiftConfig:
    return NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always", "DF_RABBITMQ_URL": "mq.example:5672"}, docker_compose={}
    )


@pytest.fixture
def default_update_kwargs(directory: Path) -> dict:
    return {
        "directory": directory,
        "image": DF_SERVER_IMAGE,
        "local_image": False,
        "tag": None,
        "nightshift": None,
        "rabbitmq_url": None,
        "rabbitmq_username": "",
        "rabbitmq_password": "",
    }


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_calls_check_server_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_pulls_both_server_and_nightshift_images(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift: Mock,
    mock_resolve_nightshift_addition: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    """nightshift reuses the exact same image (DF_SERVER_IMAGE) as the server - pull it too, so a
    subsequent restart picks up the new version for the worker as well, not just the server."""
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_run.call_args == mock.call(
        ["docker", "compose", "pull", "server", "nightshift"], cwd=default_update_kwargs["directory"]
    )


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=False)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_pulls_only_the_server_and_warns_when_nightshift_declined(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_run.call_args == mock.call(
        ["docker", "compose", "pull", "server"], cwd=default_update_kwargs["directory"]
    )
    assert mock_add_nightshift_to_install.call_count == 0
    assert mock_warn_nightshift_declined.call_count == 1
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_raises_when_tag_and_custom_image_provided(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_reconcile: Mock,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        update(directory=directory, image="custom-image", local_image=False, tag="0.15.0")

    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_and_no_pull_policy(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_and_pull_policy(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_no_local_image_and_pull_policy(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_no_image_no_pull_policy(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_save.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_with_tag(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_calls_env_set_when_env_image_differs_from_provided(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_newest: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_with_custom_image_and_no_tag_uses_image_as_is(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_newest: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_call_env_set_when_image_unchanged(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_newest: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_server_image": DF_SERVER_IMAGE}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = DF_SERVER_IMAGE

    update(**default_update_kwargs)

    assert mock_env_set.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_restarts_when_confirmed(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    # nightshift shares the exact same image as the server - reconciled explicitly here too,
    # rather than relying only on start_server()'s own recreate-on-image-change behavior.
    assert mock_reconcile.call_args == ((default_update_kwargs["directory"],), {})
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_restart_when_not_confirmed(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
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
    assert mock_reconcile.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_resolves_nightshift_before_any_write(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    default_update_kwargs: dict,
) -> None:
    mock_has_nightshift_service.return_value = False
    mock_resolve_nightshift_addition.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_load.call_count == 0
    assert mock_save.call_count == 0
    assert mock_env_set.call_count == 0
    assert mock_run.call_count == 0
    assert mock_add_nightshift_to_install.call_count == 0


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_passes_nightshift_options_to_resolve(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None

    update(
        **{
            **default_update_kwargs,
            "tag": "0.15.0",
            "nightshift": True,
            "rabbitmq_url": "mq.example:5672",
            "rabbitmq_username": "df",
            "rabbitmq_password": "secret",
        }
    )

    assert mock_resolve_nightshift_addition.call_count == 1
    assert mock_resolve_nightshift_addition.call_args == mock.call(
        default_update_kwargs["directory"], True, "mq.example:5672", "df", "secret"
    )


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_adds_nightshift_before_pulling_both_images(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    nightshift_config: NightshiftConfig,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True
    mock_has_nightshift_service.return_value = False
    mock_resolve_nightshift_addition.return_value = nightshift_config
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_add_nightshift_to_install, "add_nightshift_to_install")
    _mock_manager.attach_mock(mock_run, "run")

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    directory = default_update_kwargs["directory"]
    assert _mock_manager.mock_calls == [
        mock.call.run(["docker", "pull", f"{DF_SERVER_IMAGE_HUB}:0.15.0"], cwd=directory),
        mock.call.add_nightshift_to_install(directory, nightshift_config),
        mock.call.run(["docker", "compose", "pull", "server", "nightshift"], cwd=directory),
    ]
    assert mock_warn_nightshift_declined.call_count == 0


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=False)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_pulls_local_rabbitmq_before_stopping_server(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True
    mock_resolve_nightshift_addition.return_value = NightshiftConfig(
        envs={"DF_NIGHTSHIFT_MODE": "always"}, docker_compose=DOCKER_COMPOSE_RABBITMQ
    )
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_run, "run")
    _mock_manager.attach_mock(mock_stop, "stop_server")

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    directory = default_update_kwargs["directory"]
    assert _mock_manager.mock_calls[:3] == [
        mock.call.run(["docker", "pull", f"{DF_SERVER_IMAGE_HUB}:0.15.0"], cwd=directory),
        mock.call.run(["docker", "compose", "pull", "server", "nightshift", "rabbitmq"], cwd=directory),
        mock.call.stop_server(directory),
    ]


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_warns_when_added_nightshift_not_restarted(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    nightshift_config: NightshiftConfig,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_has_nightshift_service.return_value = False
    mock_resolve_nightshift_addition.return_value = nightshift_config

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_stop.call_count == 0
    assert mock_echo.warning.call_count == 1
    assert "deepfellow server start" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_no_warning_when_restart_declined_without_changes(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_echo.warning.call_count == 0
    assert mock_warn_nightshift_declined.call_count == 0


@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_sets_nightshift_pull_policy(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    server_values: dict,
    default_update_kwargs: dict,
) -> None:
    compose = {"services": {"server": {}, "nightshift": {}, "rabbitmq": {}}}
    mock_read.return_value = server_values
    mock_load.return_value = compose
    mock_echo.confirm.return_value = False
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None

    update(**{**default_update_kwargs, "tag": "0.15.0", "local_image": True})

    assert compose["services"]["server"]["pull_policy"] == "never"
    assert compose["services"]["nightshift"]["pull_policy"] == "never"
    assert "pull_policy" not in compose["services"]["rabbitmq"]
    assert mock_save.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user", return_value=True)
@mock.patch("deepfellow.server.update.is_legacy_mongo_install", return_value=True)
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_migrates_legacy_mongo_install_before_restart(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo_to_app_user: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_migrate_mongo_to_app_user, "migrate_mongo_to_app_user")
    _mock_manager.attach_mock(mock_stop, "stop_server")
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_is_legacy_mongo_install.call_args == mock.call(default_update_kwargs["directory"])
    assert mock_migrate_mongo_to_app_user.call_count == 1
    assert mock_migrate_mongo_to_app_user.call_args == mock.call(default_update_kwargs["directory"])
    assert [name for name, _, _ in _mock_manager.mock_calls] == ["migrate_mongo_to_app_user", "stop_server"]
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install", return_value=False)
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_skips_mongo_migration_for_non_legacy_install(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo_to_app_user: Mock,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_is_legacy_mongo_install.call_count == 1
    assert mock_migrate_mongo_to_app_user.call_count == 0
    assert mock_echo.warning.call_count == 0


@pytest.mark.parametrize(
    ("migrated", "expected_warnings"),
    [
        (True, 1),
        (False, 0),
    ],
)
@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install", return_value=True)
@mock.patch("deepfellow.server.update.has_nightshift_service", return_value=True)
@mock.patch("deepfellow.server.update.resolve_nightshift_addition", return_value=None)
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_warns_mongo_account_switch_needs_restart_when_restart_declined(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_has_nightshift_service: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo_to_app_user: Mock,
    migrated: bool,
    expected_warnings: int,
    server_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = server_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_migrate_mongo_to_app_user.return_value = migrated

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_stop.call_count == 0
    assert mock_echo.warning.call_count == expected_warnings
    if expected_warnings:
        assert "deepfellow server restart" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_skips_pull_when_already_up_to_date(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_newest.return_value = newest
    mock_running_image.return_value = newest

    update(**default_update_kwargs)

    assert mock_running_image.call_args == mock.call("server", default_update_kwargs["directory"])
    assert mock_run.call_count == 0
    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.success.call_args == mock.call("DeepFellow Server is already up to date (v1.2.4).")
    assert mock_warn_nightshift_declined.call_count == 0


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_with_same_tag_as_current_skips_pull(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    current = f"{DF_SERVER_IMAGE_HUB}:0.15.0"
    mock_read.return_value = {"df_server_image": current}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_running_image.return_value = current

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_newest.call_count == 0
    assert mock_run.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_skip_warns_when_install_has_no_nightshift(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_has_nightshift_service.return_value = False
    mock_newest.return_value = newest
    mock_running_image.return_value = newest

    update(**default_update_kwargs)

    assert mock_run.call_count == 0
    assert mock_warn_nightshift_declined.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_pulls_before_writing_env_when_newer_version_available(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": f"{DF_SERVER_IMAGE_HUB}:v1.2.3"}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = False
    mock_newest.return_value = newest
    _mock_manager = Mock()
    _mock_manager.attach_mock(mock_run, "run")
    _mock_manager.attach_mock(mock_env_set, "env_set")

    update(**default_update_kwargs)

    directory = default_update_kwargs["directory"]
    assert _mock_manager.mock_calls[:2] == [
        mock.call.run(["docker", "pull", newest], cwd=directory),
        mock.call.env_set(directory / ".env", "SERVER_IMAGE", newest, quiet=False, docker_note=False),
    ]


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_write_env_when_pull_fails(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": f"{DF_SERVER_IMAGE_HUB}:v1.2.3"}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_newest.return_value = newest
    mock_run.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        update(**default_update_kwargs)

    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_offers_restart_when_env_current_but_container_runs_old_image(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = True
    mock_newest.return_value = newest
    mock_running_image.return_value = f"{DF_SERVER_IMAGE_HUB}:v1.2.3"

    update(**default_update_kwargs)

    assert mock_run.call_args_list[0] == mock.call(["docker", "pull", newest], cwd=default_update_kwargs["directory"])
    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_start.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_offers_restart_when_env_current_but_container_not_running(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = False
    mock_newest.return_value = newest
    mock_running_image.return_value = None

    update(**default_update_kwargs)

    assert mock_run.call_count == 2
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_skip_when_adding_nightshift(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    nightshift_config: NightshiftConfig,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = False
    mock_has_nightshift_service.return_value = False
    mock_resolve_nightshift_addition.return_value = nightshift_config
    mock_newest.return_value = newest
    mock_running_image.return_value = newest

    update(**default_update_kwargs)

    assert mock_add_nightshift_to_install.call_args == mock.call(default_update_kwargs["directory"], nightshift_config)
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_does_not_skip_legacy_mongo_install(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_SERVER_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_server_image": newest}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = False
    mock_is_legacy_mongo_install.return_value = True
    mock_migrate_mongo.return_value = True
    mock_newest.return_value = newest
    mock_running_image.return_value = newest

    update(**default_update_kwargs)

    assert mock_migrate_mongo.call_args == mock.call(default_update_kwargs["directory"])
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.server.update.migrate_mongo_to_app_user")
@mock.patch("deepfellow.server.update.is_legacy_mongo_install")
@mock.patch("deepfellow.server.update.get_running_service_image")
@mock.patch("deepfellow.server.update.get_newest_image_tag")
@mock.patch("deepfellow.server.update.warn_nightshift_declined")
@mock.patch("deepfellow.server.update.add_nightshift_to_install")
@mock.patch("deepfellow.server.update.resolve_nightshift_addition")
@mock.patch("deepfellow.server.update.has_nightshift_service")
@mock.patch("deepfellow.server.update.reconcile_nightshift_running_state")
@mock.patch("deepfellow.server.update.start_server")
@mock.patch("deepfellow.server.update.stop_server")
@mock.patch("deepfellow.server.update.run")
@mock.patch("deepfellow.server.update.env_set")
@mock.patch("deepfellow.server.update.save_compose_file")
@mock.patch("deepfellow.server.update.load_compose_file")
@mock.patch("deepfellow.server.update.echo")
@mock.patch("deepfellow.server.update.read_env_file_to_dict")
@mock.patch("deepfellow.server.update.assert_docker")
@mock.patch("deepfellow.server.update.check_server_directory")
def test_update_local_image_does_not_pull_image_directly(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_echo: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_stop: Mock,
    mock_start: Mock,
    mock_reconcile: Mock,
    mock_has_nightshift_service: Mock,
    mock_resolve_nightshift_addition: Mock,
    mock_add_nightshift_to_install: Mock,
    mock_warn_nightshift_declined: Mock,
    mock_newest: Mock,
    mock_running_image: Mock,
    mock_is_legacy_mongo_install: Mock,
    mock_migrate_mongo: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_server_image": "local-image"}
    mock_load.return_value = compose_data
    mock_has_nightshift_service.return_value = True
    mock_resolve_nightshift_addition.return_value = None
    mock_is_legacy_mongo_install.return_value = False
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "image": "local-image", "local_image": True})

    assert mock_newest.call_count == 0
    assert mock_running_image.call_count == 0
    assert mock_run.call_args_list == [
        mock.call(["docker", "compose", "pull", "server", "nightshift"], cwd=default_update_kwargs["directory"])
    ]
