# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.defaults import (
    DF_WORKSPACE_IMAGE,
    DF_WORKSPACE_IMAGE_HUB,
    MONGO_IMAGE,
    WORKSPACE_MONGO_SERVICE,
    WORKSPACE_REDIS_IMAGE,
    WORKSPACE_REDIS_SERVICE,
)
from deepfellow.common.docker import DockerError, load_compose_file, save_compose_file
from deepfellow.common.exceptions import InstallError
from deepfellow.workspace.update import update
from deepfellow.workspace.utils.images import image_version
from deepfellow.workspace.utils.install import current_service_images, read_existing_env, write_stack

OLD_IMAGE = "hub.simplito.com/deepfellow/deepfellow-workspace:v0.7.0"


def _set_service_image(directory: Path, service: str, image: str) -> None:
    compose = load_compose_file(directory / "compose.yaml")
    compose["services"][service]["image"] = image
    save_compose_file(compose, directory / "compose.yaml")


def _pulled(mock_run: Mock) -> list[str]:
    return [call.args[0][2] for call in mock_run.call_args_list if call.args[0][1] == "pull"]


def _inspected(mock_run: Mock) -> list[str]:
    return [call.args[0][3] for call in mock_run.call_args_list if call.args[0][1:3] == ["image", "inspect"]]


@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_exits_without_installation(mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path):
    with pytest.raises(typer.Exit):
        update(directory=tmp_path / "missing", image=None, tag=None, local_image=None)

    assert mock_assert_docker.call_count == 0


@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
def test_update_rejects_image_and_tag_together(mock_assert_docker: Mock, mock_run: Mock, workspace_dir: Path):
    with pytest.raises(typer.BadParameter):
        update(directory=workspace_dir, image="img:1", tag="v1.0.0", local_image=None)

    assert mock_run.call_count == 0
    assert read_existing_env(workspace_dir)["DF_WORKSPACE_IMAGE"] == OLD_IMAGE


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_default_targets_pinned_image(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert read_existing_env(workspace_dir)["DF_WORKSPACE_IMAGE"] == DF_WORKSPACE_IMAGE
    assert load_compose_file(workspace_dir / "compose.yaml")["services"]["workspace"]["image"] == DF_WORKSPACE_IMAGE


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_tag_builds_hub_reference(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):

    update(directory=workspace_dir, image=None, tag="v0.8.0", local_image=None)

    assert read_existing_env(workspace_dir)["DF_WORKSPACE_IMAGE"] == f"{DF_WORKSPACE_IMAGE_HUB}:v0.8.0"


@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_refuses_downgrade_of_default_target(
    mock_echo: Mock, mock_assert_docker: Mock, mock_run: Mock, tmp_path: Path, installed_env: dict[str, str]
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": f"{DF_WORKSPACE_IMAGE_HUB}:v9.0.0"})
    env_before = (tmp_path / ".env").read_bytes()
    compose_before = (tmp_path / "compose.yaml").read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert exc_info.value.exit_code == 1
    assert "cli update" in str(mock_echo.error.call_args.args[0])
    assert mock_run.call_count == 0
    assert (tmp_path / ".env").read_bytes() == env_before
    assert (tmp_path / "compose.yaml").read_bytes() == compose_before


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=None)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_allows_explicit_older_tag(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": f"{DF_WORKSPACE_IMAGE_HUB}:v9.0.0"})

    update(directory=tmp_path, image=None, tag="v0.7.1", local_image=None)

    assert read_existing_env(tmp_path)["DF_WORKSPACE_IMAGE"] == f"{DF_WORKSPACE_IMAGE_HUB}:v0.7.1"


@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=DF_WORKSPACE_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_reports_up_to_date_without_changes(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})
    env_before = (tmp_path / ".env").read_bytes()

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert "already up to date" in str(mock_echo.success.call_args.args[0])
    assert mock_run.call_count == 0
    assert mock_echo.confirm.call_count == 0
    assert (tmp_path / ".env").read_bytes() == env_before


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_proceeds_when_running_container_is_older(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert DF_WORKSPACE_IMAGE in _pulled(mock_run)
    assert mock_offer_restart.call_args == mock.call(tmp_path, "update")


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=DF_WORKSPACE_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_proceeds_when_only_redis_image_is_newer(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})
    _set_service_image(tmp_path, WORKSPACE_REDIS_SERVICE, "redis:7.4")

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert current_service_images(tmp_path)[WORKSPACE_REDIS_SERVICE] == WORKSPACE_REDIS_IMAGE


@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run", side_effect=DockerError("pull failed"))
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_pull_failure_leaves_files_unchanged(
    mock_echo: Mock, mock_assert_docker: Mock, mock_run: Mock, mock_running_image: Mock, workspace_dir: Path
):
    env_before = (workspace_dir / ".env").read_bytes()
    compose_before = (workspace_dir / "compose.yaml").read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert exc_info.value.exit_code == 1
    assert (workspace_dir / ".env").read_bytes() == env_before
    assert (workspace_dir / "compose.yaml").read_bytes() == compose_before


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_pulls_every_image_of_new_stack(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert sorted(_pulled(mock_run)) == sorted([DF_WORKSPACE_IMAGE, MONGO_IMAGE, WORKSPACE_REDIS_IMAGE])


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_keeps_secrets_and_values(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    before = read_existing_env(workspace_dir)

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    after = read_existing_env(workspace_dir)
    assert {key: value for key, value in after.items() if key != "DF_WORKSPACE_IMAGE"} == {
        key: value for key, value in before.items() if key != "DF_WORKSPACE_IMAGE"
    }
    assert after["MCP_AUTH_TOKEN"] == "mcp-Pa$word#1-1234567890"


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.utils.images.echo")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_mongo_major_declined_updates_app_only(
    mock_echo: Mock,
    mock_images_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    _set_service_image(workspace_dir, WORKSPACE_MONGO_SERVICE, "mongo:7.0.14")
    mock_images_echo.confirm.return_value = False

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert current_service_images(workspace_dir)[WORKSPACE_MONGO_SERVICE] == "mongo:7.0.14"
    assert read_existing_env(workspace_dir)["DF_WORKSPACE_IMAGE"] == DF_WORKSPACE_IMAGE
    assert "mongo:7.0.14" in _pulled(mock_run)


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.choose_mongo_image")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_external_mongo_asks_nothing(
    mock_echo: Mock,
    mock_choose_mongo_image: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "MONGO_DB_URL": "mongodb://db.example.com:27017/?replicaSet=rs0"})

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert mock_choose_mongo_image.call_count == 0
    assert WORKSPACE_MONGO_SERVICE not in load_compose_file(tmp_path / "compose.yaml")["services"]


@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.utils.install.echo")
def test_update_exits_without_env_file(mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path):
    (tmp_path / "compose.yaml").write_text("services: {}")

    with pytest.raises(typer.Exit):
        update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert "workspace install" in str(mock_echo.error.call_args.args[0])


@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_invalid_stack_setting_exits_before_pull(
    mock_echo: Mock, mock_assert_docker: Mock, mock_run: Mock, mock_running_image: Mock, workspace_dir: Path
):
    env_file = workspace_dir / ".env"
    env_file.write_text(env_file.read_text().replace('DF_WORKSPACE_PORT="3000"', 'DF_WORKSPACE_PORT="abc"'))

    with pytest.raises(typer.Exit) as exc_info:
        update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert exc_info.value.exit_code == 1
    assert "DF_WORKSPACE_PORT" in str(mock_echo.error.call_args.args[0])
    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=None)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_proceeds_when_container_is_stopped(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert DF_WORKSPACE_IMAGE in _pulled(mock_run)
    assert "already up to date" not in str(mock_echo.success.call_args.args[0])


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=DF_WORKSPACE_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.utils.images.echo")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_asks_mongo_again_when_only_mongo_is_behind(
    mock_echo: Mock,
    mock_images_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})
    _set_service_image(tmp_path, WORKSPACE_MONGO_SERVICE, "mongo:7.0.14")
    env_before = (tmp_path / ".env").read_bytes()
    compose_before = (tmp_path / "compose.yaml").read_bytes()
    mock_images_echo.confirm.return_value = False

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert mock_images_echo.confirm.call_count == 1
    assert "already up to date" in mock_echo.success.call_args.args[0]
    assert mock_run.call_count == 0
    assert mock_offer_restart.call_count == 0
    assert (tmp_path / ".env").read_bytes() == env_before
    assert (tmp_path / "compose.yaml").read_bytes() == compose_before


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=DF_WORKSPACE_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.utils.images.echo")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_moves_mongo_when_accepted_and_only_mongo_is_behind(
    mock_echo: Mock,
    mock_images_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    tmp_path: Path,
    installed_env: dict[str, str],
):
    write_stack(tmp_path, {**installed_env, "DF_WORKSPACE_IMAGE": DF_WORKSPACE_IMAGE})
    _set_service_image(tmp_path, WORKSPACE_MONGO_SERVICE, "mongo:7.0.14")
    mock_images_echo.confirm.return_value = True

    update(directory=tmp_path, image=None, tag=None, local_image=None)

    assert current_service_images(tmp_path)[WORKSPACE_MONGO_SERVICE] == MONGO_IMAGE
    assert MONGO_IMAGE in _pulled(mock_run)
    assert mock_offer_restart.call_count == 1


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.utils.images.echo")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_moves_mongo_within_same_major_without_question(
    mock_echo: Mock,
    mock_images_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    version = image_version(MONGO_IMAGE)
    assert version is not None
    _set_service_image(workspace_dir, WORKSPACE_MONGO_SERVICE, f"mongo:{version[0]}.0.0")

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert current_service_images(workspace_dir)[WORKSPACE_MONGO_SERVICE] == MONGO_IMAGE
    assert MONGO_IMAGE in _pulled(mock_run)
    assert mock_images_echo.confirm.call_count == 0


@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_unreadable_compose_exits_before_pull(
    mock_echo: Mock, mock_assert_docker: Mock, mock_run: Mock, workspace_dir: Path
):
    (workspace_dir / "compose.yaml").write_text("services: [unclosed")

    with pytest.raises(typer.Exit) as exc_info:
        update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert exc_info.value.exit_code == 1
    assert "Cannot read" in str(mock_echo.error.call_args.args[0])
    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.write_stack", side_effect=InstallError("Could not write"))
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_write_failure_exits_without_restart(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_write_stack: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    with pytest.raises(typer.Exit) as exc_info:
        update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call("Could not write")
    assert mock_offer_restart.call_count == 0


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_local_image_is_kept_and_not_pulled(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    update(directory=workspace_dir, image="my/workspace:dev", tag=None, local_image=True)

    env = read_existing_env(workspace_dir)
    assert env["DF_WORKSPACE_IMAGE"] == "my/workspace:dev"
    assert env["DF_WORKSPACE_LOCAL_IMAGE"] == "true"
    assert load_compose_file(workspace_dir / "compose.yaml")["services"]["workspace"]["pull_policy"] == "never"
    assert "my/workspace:dev" not in _pulled(mock_run)


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value="my/workspace:dev")
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_local_image_without_image_keeps_installed_one(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    update(directory=workspace_dir, image="my/workspace:dev", tag=None, local_image=True)

    update(directory=workspace_dir, image=None, tag=None, local_image=None)

    assert read_existing_env(workspace_dir)["DF_WORKSPACE_IMAGE"] == "my/workspace:dev"


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value="my/workspace:dev")
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_no_local_image_goes_back_to_registry_image(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    update(directory=workspace_dir, image="my/workspace:dev", tag=None, local_image=True)

    update(directory=workspace_dir, image=None, tag=None, local_image=False)

    env = read_existing_env(workspace_dir)
    assert env["DF_WORKSPACE_IMAGE"] == DF_WORKSPACE_IMAGE
    assert "DF_WORKSPACE_LOCAL_IMAGE" not in env
    assert "pull_policy" not in load_compose_file(workspace_dir / "compose.yaml")["services"]["workspace"]


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_local_image_is_checked_to_exist_instead_of_pulled(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    update(directory=workspace_dir, image="my/workspace:dev", tag=None, local_image=True)

    assert _inspected(mock_run) == ["my/workspace:dev"]
    assert "my/workspace:dev" not in _pulled(mock_run)


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value=OLD_IMAGE)
@mock.patch("deepfellow.workspace.update.run", side_effect=DockerError("No such image"))
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_missing_local_image_leaves_files_unchanged_and_does_not_restart(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    env_before = (workspace_dir / ".env").read_bytes()
    compose_before = (workspace_dir / "compose.yaml").read_bytes()

    with pytest.raises(typer.Exit) as exc_info:
        update(directory=workspace_dir, image="ws:typo", tag=None, local_image=True)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_args == mock.call("Local image ws:typo not found; nothing was changed.")
    assert (workspace_dir / ".env").read_bytes() == env_before
    assert (workspace_dir / "compose.yaml").read_bytes() == compose_before
    assert mock_offer_restart.call_count == 0


@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
def test_update_rejects_tag_with_explicit_local_image(mock_assert_docker: Mock, mock_run: Mock, workspace_dir: Path):
    with pytest.raises(typer.BadParameter, match="--tag"):
        update(directory=workspace_dir, image=None, tag="v0.9.0", local_image=True)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.workspace.update.offer_restart")
@mock.patch("deepfellow.workspace.update.get_running_service_image", return_value="my/workspace:dev")
@mock.patch("deepfellow.workspace.update.run")
@mock.patch("deepfellow.workspace.update.assert_docker")
@mock.patch("deepfellow.workspace.update.echo")
def test_update_tag_over_an_inherited_local_image_switches_to_the_registry(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_run: Mock,
    mock_running_image: Mock,
    mock_offer_restart: Mock,
    workspace_dir: Path,
):
    update(directory=workspace_dir, image="my/workspace:dev", tag=None, local_image=True)

    update(directory=workspace_dir, image=None, tag="v0.9.0", local_image=None)

    env = read_existing_env(workspace_dir)
    assert env["DF_WORKSPACE_IMAGE"] == f"{DF_WORKSPACE_IMAGE_HUB}:v0.9.0"
    assert "DF_WORKSPACE_LOCAL_IMAGE" not in env
    assert f"{DF_WORKSPACE_IMAGE_HUB}:v0.9.0" in _pulled(mock_run)
