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

from deepfellow.infra.uninstall import _ALREADY_UNINSTALLED_IMAGES_MESSAGE, _ALREADY_UNINSTALLED_MESSAGE, uninstall

_IMAGES_COMMAND = ["docker", "compose", "images", "--format", "json"]
_RM_COMMAND = ["docker", "compose", "rm", "-s", "-f"]


@pytest.fixture
def directory_with_env(tmp_path: Path) -> Path:
    (tmp_path / ".env").write_text("")
    return tmp_path


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_calls_check_infra_directory_and_assert_docker(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = [None, None]

    uninstall(directory=directory, remove_images=False)

    assert mock_check.call_count == 1
    assert mock_check.call_args == mock.call(directory, missing_message=_ALREADY_UNINSTALLED_MESSAGE)
    assert mock_assert_docker.call_count == 1
    assert mock_assert_docker.call_args == mock.call()


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_turns_off_stack_and_removes_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = [None, None]

    uninstall(directory=directory, remove_images=False)

    assert mock_run.call_count == 2
    assert mock_run.call_args_list[0] == mock.call(_IMAGES_COMMAND, cwd=directory, capture_output=True, check=False)
    assert mock_run.call_args_list[1] == mock.call(_RM_COMMAND, directory, quiet=True)
    assert mock_rmtree.call_count == 1
    assert mock_rmtree.call_args == mock.call(directory)
    assert mock_echo.success.call_count == 1
    assert mock_echo.success.call_args == mock.call("DeepFellow Infra uninstalled.")


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_keeps_images_when_remove_images_declined(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    images_output = '[{"Repository": "hub.simplito.com/deepfellow/deepfellow-infra", "Tag": "v0.30.0"}]'
    mock_run.side_effect = [images_output, None]

    uninstall(directory=directory, remove_images=False)

    assert mock_run.call_count == 2
    assert mock.call(["docker", "image", "rm", mock.ANY], quiet=True, check=False) not in mock_run.call_args_list
    assert mock.call("Docker images were not removed.") in mock_echo.info.call_args_list
    assert mock_echo.info.call_args_list[-1] == mock.call("Removing DeepFellow Infra files.")


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_asks_interactively_when_remove_images_not_given(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = [None, None]
    mock_echo.confirm.return_value = False

    uninstall(directory=directory, remove_images=None)

    assert mock_check.call_args == mock.call(directory, missing_message=_ALREADY_UNINSTALLED_MESSAGE)
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call("Also remove Docker images?")


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_removes_images_collected_from_docker_compose(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    images_output = '[{"Repository": "hub.simplito.com/deepfellow/deepfellow-infra", "Tag": "v0.30.0"}]'
    mock_run.side_effect = [images_output, None, None]

    uninstall(directory=directory, remove_images=True)

    assert mock_check.call_args == mock.call(directory, missing_message=_ALREADY_UNINSTALLED_IMAGES_MESSAGE)
    assert mock_run.call_count == 3
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "image", "rm", "hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0"], quiet=True, check=False
    )
    assert mock.call("Removing DeepFellow Infra Docker images.") in mock_echo.info.call_args_list
    assert mock_echo.info.call_args_list[-1] == mock.call("Removing DeepFellow Infra files.")


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_removes_images_before_removing_directory(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    images_output = '[{"Repository": "hub.simplito.com/deepfellow/deepfellow-infra", "Tag": "v0.30.0"}]'
    call_order: list[str] = []

    def run_side_effect(command: list[str], *args: object, **kwargs: object) -> str | None:
        if command == _IMAGES_COMMAND:
            return images_output
        if command == _RM_COMMAND:
            return None
        call_order.append("remove_image")
        return None

    mock_run.side_effect = run_side_effect
    mock_rmtree.side_effect = lambda _directory: call_order.append("remove_directory")

    uninstall(directory=directory, remove_images=True)

    assert call_order == ["remove_image", "remove_directory"]


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_treats_null_images_output_as_no_images(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = ["null", None]

    uninstall(directory=directory, remove_images=True)

    assert mock_run.call_count == 2


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_treats_empty_images_output_as_no_images(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = [None, None]

    uninstall(directory=directory, remove_images=True)

    assert mock_run.call_count == 2


@mock.patch("deepfellow.infra.uninstall.read_env_file")
@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_removes_df_infra_image_from_env_file(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_read_env_file: Mock,
    directory_with_env: Path,
) -> None:
    mock_run.side_effect = [None, None, None]
    mock_read_env_file.return_value = {"DF_INFRA_IMAGE": "hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0"}

    uninstall(directory=directory_with_env, remove_images=True)

    assert mock_read_env_file.call_count == 1
    assert mock_read_env_file.call_args == mock.call(directory_with_env / ".env")
    assert mock_run.call_count == 3
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "image", "rm", "hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0"], quiet=True, check=False
    )


@mock.patch("deepfellow.infra.uninstall.read_env_file")
@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_skips_env_file_without_df_infra_image(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_read_env_file: Mock,
    directory_with_env: Path,
) -> None:
    mock_run.side_effect = [None, None]
    mock_read_env_file.return_value = {}

    uninstall(directory=directory_with_env, remove_images=True)

    assert mock_run.call_count == 2


@mock.patch("deepfellow.infra.uninstall.read_env_file")
@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_skips_read_env_file_when_env_file_missing(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_read_env_file: Mock,
    directory: Path,
) -> None:
    mock_run.side_effect = [None, None]

    uninstall(directory=directory, remove_images=False)

    assert mock_read_env_file.call_count == 0


@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_removes_every_image_collected_from_docker_compose(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    directory: Path,
) -> None:
    images_output = (
        '[{"Repository": "hub.simplito.com/deepfellow/deepfellow-infra", "Tag": "v0.30.0"}, '
        '{"Repository": "milvusdb/milvus", "Tag": "v2.4.0"}]'
    )
    mock_run.side_effect = [images_output, None, None, None]

    uninstall(directory=directory, remove_images=True)

    assert mock_run.call_count == 4
    removed_images = {call.args[0][3] for call in mock_run.call_args_list[2:]}
    assert removed_images == {"hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0", "milvusdb/milvus:v2.4.0"}
    for call in mock_run.call_args_list[2:]:
        assert call.kwargs == {"quiet": True, "check": False}


@mock.patch("deepfellow.infra.uninstall.read_env_file")
@mock.patch("deepfellow.infra.uninstall.rmtree")
@mock.patch("deepfellow.infra.uninstall.run")
@mock.patch("deepfellow.infra.uninstall.echo")
@mock.patch("deepfellow.infra.uninstall.assert_docker")
@mock.patch("deepfellow.infra.uninstall.check_infra_directory")
def test_uninstall_deduplicates_image_reported_by_both_compose_and_env_file(
    mock_check: Mock,
    mock_assert_docker: Mock,
    mock_echo: Mock,
    mock_run: Mock,
    mock_rmtree: Mock,
    mock_read_env_file: Mock,
    directory_with_env: Path,
) -> None:
    images_output = '[{"Repository": "hub.simplito.com/deepfellow/deepfellow-infra", "Tag": "v0.30.0"}]'
    mock_run.side_effect = [images_output, None, None]
    mock_read_env_file.return_value = {"DF_INFRA_IMAGE": "hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0"}

    uninstall(directory=directory_with_env, remove_images=True)

    assert mock_run.call_count == 3
    assert mock_run.call_args_list[2] == mock.call(
        ["docker", "image", "rm", "hub.simplito.com/deepfellow/deepfellow-infra:v0.30.0"], quiet=True, check=False
    )
