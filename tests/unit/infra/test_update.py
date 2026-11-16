# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import (
    DF_INFRA_IMAGE_HUB,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    INFRA_BIND_ADDRESS,
)
from deepfellow.common.tls import CAError
from deepfellow.infra.update import _resolve_image, update

DF_INFRA_IMAGE = f"{DF_INFRA_IMAGE_HUB}:1.2.3"

pytestmark = pytest.mark.usefixtures("_unversioned_cli")


@pytest.fixture
def infra_values() -> dict:
    return {"df_infra_image": "some-image"}


@pytest.fixture
def compose_data() -> dict:
    return {"services": {"infra": {}}}


@pytest.fixture
def compose_data_with_pull_policy() -> dict:
    return {"services": {"infra": {"pull_policy": "always"}}}


@pytest.fixture
def default_update_kwargs(directory) -> dict:
    return {
        "directory": directory,
        "image": None,
        "local_image": False,
        "tag": None,
    }


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_calls_check_infra_directory(
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_check.call_count == 1
    assert mock_check.call_args == ((default_update_kwargs["directory"],), {})
    assert mock_assert_docker.call_count == 1


def test_resolve_image_returns_hub_image_when_tag_provided() -> None:
    result: str = _resolve_image("custom-image", "0.15.0")

    assert result == f"{DF_INFRA_IMAGE_HUB}:0.15.0"


@mock.patch("deepfellow.common.version.cli_version", return_value="1.2.0")
def test_resolve_image_exits_when_tag_is_newer_than_cli(mock_cli_version: Mock) -> None:
    with pytest.raises(typer.Exit):
        _resolve_image("custom-image", "1.3.0")


@mock.patch("deepfellow.common.version.cli_version", return_value="1.2.0")
def test_resolve_image_allows_newer_tag_for_local_image(mock_cli_version: Mock) -> None:
    result: str = _resolve_image("custom:2.0.0", None, local_image=True)

    assert result == "custom:2.0.0"


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_returns_newest_when_default_image_and_no_tag(mock_get_newest_image_tag: Mock) -> None:
    mock_get_newest_image_tag.return_value = f"{DF_INFRA_IMAGE_HUB}:0.16.0"

    result: str = _resolve_image(None, None)

    assert result == f"{DF_INFRA_IMAGE_HUB}:0.16.0"
    assert mock_get_newest_image_tag.call_count == 1
    assert mock_get_newest_image_tag.call_args == mock.call(DF_INFRA_IMAGE_HUB)


def test_resolve_image_returns_image_when_custom_image_and_no_tag() -> None:
    result: str = _resolve_image("custom-image", None)

    assert result == "custom-image"


@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_raises_when_tag_and_custom_image_provided(
    mock_check: Mock,
    mock_assert_docker: Mock,
    directory: Path,
) -> None:
    with pytest.raises(typer.BadParameter):
        update(directory=directory, image="custom-image", local_image=False, tag="0.15.0")

    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "image": "local-image:dev", "local_image": True})

    assert compose_data["services"]["infra"]["pull_policy"] == "never"
    assert mock_save.call_count == 1
    assert mock_save.call_args == (
        (compose_data, default_update_kwargs["directory"] / DOCKER_COMPOSE_CONFIG_FILENAME),
        {},
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data_with_pull_policy: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data_with_pull_policy
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "image": "local-image:dev", "local_image": True})

    assert compose_data_with_pull_policy["services"]["infra"]["pull_policy"] == "always"
    assert mock_save.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data_with_pull_policy: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data_with_pull_policy
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert "pull_policy" not in compose_data_with_pull_policy["services"]["infra"]
    assert mock_save.call_count == 1
    assert mock_save.call_args == (
        (compose_data_with_pull_policy, default_update_kwargs["directory"] / DOCKER_COMPOSE_CONFIG_FILENAME),
        {},
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_save.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == (
        (mock.ANY, "INFRA_IMAGE", f"{DF_INFRA_IMAGE_HUB}:0.15.0"),
        {"quiet": False, "docker_note": False},
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = DF_INFRA_IMAGE

    update(**default_update_kwargs)

    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == (
        (mock.ANY, "INFRA_IMAGE", DF_INFRA_IMAGE),
        {"quiet": False, "docker_note": False},
    )
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_infra_image": DF_INFRA_IMAGE}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = DF_INFRA_IMAGE

    update(**default_update_kwargs)

    assert mock_env_set.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True

    update(**default_update_kwargs)

    assert mock_stop.call_count == 1
    assert mock_stop.call_args == ((default_update_kwargs["directory"],), {})
    assert mock_start.call_count == 1
    assert mock_start.call_args == ((default_update_kwargs["directory"],), {})
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    infra_values: dict,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_stop.call_count == 0
    assert mock_start.call_count == 0
    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    mock_newest: Mock,
    mock_running_image: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    current = f"{DF_INFRA_IMAGE_HUB}:v1.2.3"
    mock_read.return_value = {"df_infra_image": current}
    mock_load.return_value = compose_data
    mock_running_image.return_value = current
    mock_newest.return_value = current

    update(**default_update_kwargs)

    assert mock_run.call_count == 0
    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_pulls_when_newer_version_available(
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
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_INFRA_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_infra_image": f"{DF_INFRA_IMAGE_HUB}:v1.2.3"}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = newest

    update(**default_update_kwargs)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "pull", newest], cwd=default_update_kwargs["directory"])
    assert mock_env_set.call_count == 1
    assert mock_env_set.call_args == ((mock.ANY, "INFRA_IMAGE", newest), {"quiet": False, "docker_note": False})


@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_with_same_tag_as_current_still_pulls(
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
    mock_running_image: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_infra_image": f"{DF_INFRA_IMAGE_HUB}:0.15.0"}
    mock_load.return_value = compose_data
    mock_running_image.return_value = f"{DF_INFRA_IMAGE_HUB}:0.15.0"

    update(**{**default_update_kwargs, "tag": "0.15.0"})

    assert mock_run.call_args == mock.call(
        ["docker", "pull", f"{DF_INFRA_IMAGE_HUB}:0.15.0"], cwd=default_update_kwargs["directory"]
    )


@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    mock_newest: Mock,
    mock_running_image: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_INFRA_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_infra_image": f"{DF_INFRA_IMAGE_HUB}:v1.2.3"}
    mock_load.return_value = compose_data
    mock_newest.return_value = newest
    mock_run.side_effect = typer.Exit(1)

    with pytest.raises(typer.Exit):
        update(**default_update_kwargs)

    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    mock_newest: Mock,
    mock_running_image: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_INFRA_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_infra_image": newest}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = True
    mock_newest.return_value = newest
    mock_running_image.return_value = f"{DF_INFRA_IMAGE_HUB}:v1.2.3"

    update(**default_update_kwargs)

    assert mock_run.call_args == mock.call(["docker", "pull", newest], cwd=default_update_kwargs["directory"])
    assert mock_env_set.call_count == 0
    assert mock_echo.confirm.call_count == 1
    assert mock_stop.call_count == 1
    assert mock_start.call_count == 1


@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
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
    mock_newest: Mock,
    mock_running_image: Mock,
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_INFRA_IMAGE_HUB}:v1.2.4"
    mock_read.return_value = {"df_infra_image": newest}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False
    mock_newest.return_value = newest
    mock_running_image.return_value = None

    update(**default_update_kwargs)

    assert mock_running_image.call_args == mock.call("infra", default_update_kwargs["directory"])
    assert mock_run.call_count == 1
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_local_image_does_not_pull(
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
    compose_data: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = {"df_infra_image": "local-image"}
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**{**default_update_kwargs, "image": "local-image:dev", "local_image": True})

    assert mock_run.call_count == 0
    assert mock_newest.call_count == 0


@mock.patch("deepfellow.infra.update.start_infra")
@mock.patch("deepfellow.infra.update.stop_infra")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_binds_infra_port_of_install_from_before_bind_addresses(
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
    infra_values: dict,
    default_update_kwargs: dict,
) -> None:
    compose_data = {"services": {"infra": {"ports": ["${DF_INFRA_PORT}:8086"]}}}
    mock_read.return_value = infra_values
    mock_load.return_value = compose_data
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert compose_data["services"]["infra"]["ports"] == [f"{INFRA_BIND_ADDRESS}:${{DF_INFRA_PORT}}:8086"]
    assert mock_save.call_count == 1


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_exits_when_installed_is_newer_than_newest_compatible(mock_get_newest_image_tag: Mock) -> None:
    mock_get_newest_image_tag.return_value = f"{DF_INFRA_IMAGE_HUB}:1.2.0"

    with pytest.raises(typer.Exit):
        _resolve_image(None, None, f"{DF_INFRA_IMAGE_HUB}:1.3.0")


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_allows_explicit_older_tag_as_downgrade(mock_get_newest_image_tag: Mock) -> None:
    result: str = _resolve_image(None, "1.1.0", f"{DF_INFRA_IMAGE_HUB}:1.3.0")

    assert result == f"{DF_INFRA_IMAGE_HUB}:1.1.0"
    assert mock_get_newest_image_tag.call_count == 0


@mock.patch("deepfellow.common.version.cli_version", return_value="1.2.0")
def test_resolve_image_skips_compat_check_when_skip_version_check(mock_cli_version: Mock) -> None:
    result: str = _resolve_image("custom-image", "1.3.0", skip_version_check=True)

    assert result == f"{DF_INFRA_IMAGE_HUB}:1.3.0"


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_skips_downgrade_check_when_skip_version_check(mock_get_newest_image_tag: Mock) -> None:
    mock_get_newest_image_tag.return_value = f"{DF_INFRA_IMAGE_HUB}:1.2.0"

    result: str = _resolve_image(None, None, f"{DF_INFRA_IMAGE_HUB}:1.3.0", skip_version_check=True)

    assert result == f"{DF_INFRA_IMAGE_HUB}:1.2.0"


@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_uses_local_image_without_registry_or_checks(
    mock_get_newest_image_tag: Mock, mock_echo: Mock
) -> None:
    result: str = _resolve_image(DF_INFRA_IMAGE, None, f"{DF_INFRA_IMAGE_HUB}:1.3.0", local_image=True)

    assert result == DF_INFRA_IMAGE
    assert mock_get_newest_image_tag.call_count == 0
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_uses_hub_tag_for_local_image_with_tag(mock_get_newest_image_tag: Mock) -> None:
    result: str = _resolve_image(None, "dev-build", local_image=True)

    assert result == f"{DF_INFRA_IMAGE_HUB}:dev-build"
    assert mock_get_newest_image_tag.call_count == 0


@pytest.mark.parametrize(
    "image", [pytest.param("custom/image:dev", id="non-version-tag"), pytest.param("custom/image", id="no-tag")]
)
@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.common.version.cli_version", return_value="1.2.0")
def test_resolve_image_exits_when_custom_image_version_cannot_be_checked(
    mock_cli_version: Mock, mock_echo: Mock, image: str
) -> None:
    with pytest.raises(typer.Exit):
        _resolve_image(image, None)

    assert "--skip-version-check" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.common.version.cli_version", return_value="1.2.0")
def test_resolve_image_warns_when_version_check_is_skipped(mock_cli_version: Mock, mock_echo: Mock) -> None:
    with mock.patch("deepfellow.common.registry.echo") as registry_echo:
        _resolve_image("custom/image:dev", None, skip_version_check=True)

    assert registry_echo.warning.call_count == 1
    assert "--skip-version-check" in registry_echo.warning.call_args.args[0]


@mock.patch("deepfellow.common.version.cli_version", return_value="0.38.0")
@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_refuses_incompatible_tag_before_changing_anything(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_read: Mock,
    mock_load: Mock,
    mock_save: Mock,
    mock_registry_echo: Mock,
    mock_cli_version: Mock,
    infra_values: dict,
    default_update_kwargs: dict,
) -> None:
    mock_read.return_value = infra_values

    with pytest.raises(typer.Exit):
        update(**{**default_update_kwargs, "tag": "0.39.0"})

    assert mock_load.call_count == 0
    assert mock_save.call_count == 0


@mock.patch("deepfellow.infra.update.refresh_ca_trust_bundle")
@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_refreshes_ca_bundle_when_already_up_to_date(
    mock_check_infra_directory: Mock,
    mock_assert_docker: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_echo: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_get_newest_image_tag: Mock,
    mock_get_running_service_image: Mock,
    mock_refresh_ca_trust_bundle: Mock,
    default_update_kwargs: dict,
) -> None:
    current = f"{DF_INFRA_IMAGE_HUB}:v1.2.3"
    infra_service = {"ports": [f"{INFRA_BIND_ADDRESS}:8086:8086"], "volumes": ["/fake/dir/trust:/trust:ro"]}
    mock_read_env_file_to_dict.return_value = {"df_infra_image": current}
    mock_load_compose_file.return_value = {"services": {"infra": infra_service}}
    mock_get_newest_image_tag.return_value = current
    mock_get_running_service_image.return_value = current

    update(**default_update_kwargs)

    assert mock_run.call_count == 0
    assert mock_refresh_ca_trust_bundle.call_count == 1
    assert mock_refresh_ca_trust_bundle.call_args == mock.call(default_update_kwargs["directory"], infra_service)


@mock.patch("deepfellow.common.docker.write_ca_bundle")
@mock.patch("deepfellow.infra.update.get_running_service_image")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_does_not_add_trust_to_legacy_install(
    mock_check_infra_directory: Mock,
    mock_assert_docker: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_echo: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_get_newest_image_tag: Mock,
    mock_get_running_service_image: Mock,
    mock_write_ca_bundle: Mock,
    default_update_kwargs: dict,
) -> None:
    current = f"{DF_INFRA_IMAGE_HUB}:v1.2.3"
    mock_read_env_file_to_dict.return_value = {"df_infra_image": current}
    mock_load_compose_file.return_value = {
        "services": {"infra": {"ports": ["8086:8086"], "environment": ["DF_NAME=${DF_NAME}"], "volumes": []}}
    }
    mock_get_newest_image_tag.return_value = current
    mock_get_running_service_image.return_value = current

    update(**default_update_kwargs)

    saved_infra = mock_save_compose_file.call_args.args[0]["services"]["infra"]
    assert mock_write_ca_bundle.call_count == 0
    assert saved_infra["volumes"] == []
    assert saved_infra["environment"] == ["DF_NAME=${DF_NAME}"]


@mock.patch("deepfellow.common.docker.echo")
@mock.patch("deepfellow.common.docker.write_ca_bundle")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
@mock.patch("deepfellow.infra.update.run")
@mock.patch("deepfellow.infra.update.env_set")
@mock.patch("deepfellow.infra.update.save_compose_file")
@mock.patch("deepfellow.infra.update.load_compose_file")
@mock.patch("deepfellow.infra.update.echo")
@mock.patch("deepfellow.infra.update.read_env_file_to_dict")
@mock.patch("deepfellow.infra.update.assert_docker")
@mock.patch("deepfellow.infra.update.check_infra_directory")
def test_update_warns_on_ca_error_and_still_pulls_and_offers_restart(
    mock_check_infra_directory: Mock,
    mock_assert_docker: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_echo: Mock,
    mock_load_compose_file: Mock,
    mock_save_compose_file: Mock,
    mock_env_set: Mock,
    mock_run: Mock,
    mock_get_newest_image_tag: Mock,
    mock_write_ca_bundle: Mock,
    mock_docker_echo: Mock,
    default_update_kwargs: dict,
) -> None:
    newest = f"{DF_INFRA_IMAGE_HUB}:v1.2.4"
    directory = default_update_kwargs["directory"]
    infra_service = {"ports": [f"{INFRA_BIND_ADDRESS}:8086:8086"], "volumes": [f"{directory}/trust:/trust:ro"]}
    mock_read_env_file_to_dict.return_value = {"df_infra_image": f"{DF_INFRA_IMAGE_HUB}:v1.2.3"}
    mock_load_compose_file.return_value = {"services": {"infra": infra_service}}
    mock_get_newest_image_tag.return_value = newest
    mock_write_ca_bundle.side_effect = CAError("The CA certificate is malformed.")
    mock_echo.confirm.return_value = False

    update(**default_update_kwargs)

    assert mock_write_ca_bundle.call_count == 1
    assert mock_write_ca_bundle.call_args == mock.call(directory / "trust")
    assert mock_docker_echo.warning.call_count == 1
    assert "The CA certificate is malformed." in mock_docker_echo.warning.call_args.args[0]
    assert mock_run.call_args == mock.call(["docker", "pull", newest], cwd=directory)
    assert mock_echo.confirm.call_args == mock.call("Do you want to restart?", default=True)


@pytest.mark.parametrize("image", [None, DF_INFRA_IMAGE_HUB])
@mock.patch("deepfellow.common.registry.echo")
@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_exits_for_local_image_without_tag(
    mock_get_newest_image_tag: Mock, mock_echo: Mock, image: str | None
) -> None:
    with pytest.raises(typer.Exit):
        _resolve_image(image, None, f"{DF_INFRA_IMAGE_HUB}:1.3.0", local_image=True)

    message = mock_echo.error.call_args.args[0]
    assert mock_get_newest_image_tag.call_count == 0
    assert message.startswith("Infra: `--local-image` needs an explicit image tag")
    assert "`--image <name>:<tag>` or `--tag <tag>`" in message


@mock.patch("deepfellow.infra.update.get_newest_image_tag")
def test_resolve_image_pins_newest_release_when_installed_image_is_latest(mock_get_newest_image_tag: Mock) -> None:
    mock_get_newest_image_tag.return_value = f"{DF_INFRA_IMAGE_HUB}:1.2.0"

    result: str = _resolve_image(None, None, f"{DF_INFRA_IMAGE_HUB}:latest")

    assert result == f"{DF_INFRA_IMAGE_HUB}:1.2.0"
