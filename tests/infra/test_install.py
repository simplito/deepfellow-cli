# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import re
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.models import OptionInfo

from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DOCKER_COMPOSE_CONFIG_FILENAME,
)
from deepfellow.common.docker import DockerError
from deepfellow.common.exceptions import InstallError
from deepfellow.common.state import state
from deepfellow.infra.install import install as install_command
from deepfellow.infra.utils.install import InstallConfig, InstallContext, apply, inspect, install, resolve


@pytest.fixture
def docker_config() -> Mock:
    m = Mock(spec=Path)
    m.is_file.return_value = True
    return m


@pytest.fixture
def install_config(directory: Path, docker_config: Mock) -> InstallConfig:
    state.cli_config_file = Mock(name="config-file")
    state.cli_secrets_file = Mock(name="secrets-file")
    return InstallConfig(
        directory=directory,
        docker_socket="/var/run/docker.sock",
        df_name=DF_INFRA_NAME,
        infra_url=DF_INFRA_URL,
        infra_port=DF_INFRA_PORT,
        df_infra_image=DF_INFRA_IMAGE,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        docker_config=docker_config,
        admin_api_key="admin-key",
        api_key="api-key",
        mesh_key="mesh-key",
        compose_prefix="dfabc123_",
        storage_dir=DF_INFRA_STORAGE_DIR,
        metrics_username="metrics-user",
        metrics_password="metrics-pass",
        hugging_face_token=None,
        civitai_token=None,
        local_image=False,
        print_keys=False,
        df_connect_to_mesh_url=None,
        df_connect_to_mesh_key=None,
    )


@pytest.fixture
def default_install_kwargs(directory: Path, docker_config: Mock) -> dict:
    state.cli_config_file = Mock(name="config-file")
    state.cli_secrets_file = Mock(name="secrets-file")
    return {
        "directory": directory,
        "port": DF_INFRA_PORT,
        "image": DF_INFRA_IMAGE,
        "local_image": False,
        "docker_config": docker_config,
        "storage": DF_INFRA_STORAGE_DIR,
        "hugging_face_token": None,
        "civitai_token": None,
        "infra_name": DF_INFRA_NAME,
        "infra_url": DF_INFRA_URL,
        "docker_network": DF_INFRA_DOCKER_NETWORK,
        "force_install": False,
        "allow_rootful": False,
        "allow_print_keys": None,
        "keep_compose_prefix": None,
        "keep_storage": None,
        "keep_metrics": None,
    }


def _setup_echo(mock_echo: Mock) -> None:
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.return_value = False


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_calls_assert_docker(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}

    inspect(directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False)

    assert mock_assert_docker.call_count == 1


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_passes_allow_rootful_to_get_socket(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}

    inspect(directory=directory, allow_rootful=True, force_install=False, image=DF_INFRA_IMAGE, local_image=False)

    assert mock_get_socket.call_args == mock.call(allow_rootful=True)


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_ensures_directory_with_force_install(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}

    inspect(directory=directory, allow_rootful=False, force_install=True, image=DF_INFRA_IMAGE, local_image=False)

    assert mock_ensure_directory.call_args == mock.call(
        directory, error_message="Unable to create DeepFellow Infra directory.", force_install=True
    )


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_resolves_newest_image_tag_for_default_image(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}
    mock_get_newest_image_tag.return_value = "v1.2.3"

    context = inspect(
        directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False
    )

    assert context.newest_image_tag == "v1.2.3"
    assert mock_get_newest_image_tag.call_count == 1


@pytest.mark.parametrize(
    ("image", "local_image"),
    [
        pytest.param(DF_INFRA_IMAGE, True, id="local_image"),
        pytest.param("custom/image:tag", False, id="custom_image"),
    ],
)
@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_skips_newest_image_tag_lookup(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    image: str,
    local_image: bool,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}

    context = inspect(
        directory=directory, allow_rootful=False, force_install=False, image=image, local_image=local_image
    )

    assert context.newest_image_tag is None
    assert mock_get_newest_image_tag.call_count == 0


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_returns_context_with_docker_socket_and_env_content(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {"DF_NAME": "infra"}

    context = inspect(
        directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False
    )

    assert context.directory == directory
    assert context.docker_socket == "/var/run/docker.sock"
    assert context.original_env_content == {"DF_NAME": "infra"}


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_assert_docker(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_assert_docker.call_count == 1
    assert mock_assert_docker.call_args == ((), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_get_socket_with_allow_rootful(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "allow_rootful": True})

    assert mock_get_socket.call_count == 1
    assert mock_get_socket.call_args == ((), {"allow_rootful": True})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_ensure_directory(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "force_install": True})

    assert mock_ensure_dir.call_count == 1
    assert mock_ensure_dir.call_args == (
        (directory,),
        {"error_message": mock.ANY, "force_install": True},
    )


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_read_env_file_to_dict(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_read.call_count == 1
    assert mock_read.call_args == ((directory / ".env",), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_docker_config_write_text_when_not_a_file(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    docker_config: Mock,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    docker_config.is_file.return_value = False

    install(**default_install_kwargs)

    assert docker_config.write_text.call_count == 1
    assert docker_config.write_text.call_args == (("{}",), {"encoding": "utf-8"})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_docker_config_no_write_text_when_file_exists(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    docker_config: Mock,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    docker_config.is_file.return_value = True

    install(**default_install_kwargs)

    assert docker_config.write_text.call_count == 0


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_docker_config_defaults_to_directory_path(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    tmp_path: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    dir = tmp_path

    install(**{**default_install_kwargs, "directory": dir, "docker_config": None})

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_INFRA_DOCKER_CONFIG"] == str(dir / "docker-config.json")


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_flag_print_keys_true_prints_keys(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.return_value = True
    mock_configure_uuid.return_value = "test-uuid-key"
    mock_read.return_value = {}

    install(**default_install_kwargs)

    echo_info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert any("DF_INFRA_ADMIN_API_KEY" in msg for msg in echo_info_messages)
    assert any("DF_INFRA_API_KEY" in msg for msg in echo_info_messages)
    assert any("DF_MESH_KEY" in msg for msg in echo_info_messages)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_flag_print_keys_false_does_not_print_keys(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    echo_info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert not any("DF_INFRA_ADMIN_API_KEY:" in msg for msg in echo_info_messages)
    assert not any("DF_INFRA_API_KEY:" in msg for msg in echo_info_messages)
    assert not any("DF_MESH_KEY:" in msg for msg in echo_info_messages)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_forwards_allow_print_keys_as_from_args(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "allow_print_keys": True})

    print_keys_call = mock_echo.confirm.call_args_list[0]
    assert print_keys_call.kwargs["from_args"] is True


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_forwards_keep_compose_prefix_as_from_args(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {"df_infra_compose_prefix": "dfabcdef_"}

    install(**{**default_install_kwargs, "keep_compose_prefix": False})

    compose_prefix_call = mock_echo.confirm.call_args_list[1]
    assert compose_prefix_call.kwargs["from_args"] is False


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_keep_compose_prefix_ignored_without_original(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    """keep_compose_prefix=True has no effect when there is no previous prefix to keep."""
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "keep_compose_prefix": True})

    infra_values = mock_save_env.call_args[0][1]
    assert re.match(r"^df[a-z0-9]{6}_$", infra_values["DF_INFRA_COMPOSE_PREFIX"])
    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_forwards_keep_storage_as_from_args(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {"df_infra_storage_dir": "/custom/storage"}

    install(**{**default_install_kwargs, "keep_storage": True})

    storage_call = mock_echo.confirm.call_args_list[1]
    assert storage_call.kwargs["from_args"] is True


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_forwards_keep_metrics_as_from_args(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {"df_metrics_username": "orig_user", "df_metrics_password": "orig_pass"}

    install(**{**default_install_kwargs, "keep_metrics": False})

    metrics_call = mock_echo.confirm.call_args_list[1]
    assert metrics_call.kwargs["from_args"] is False


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_ensure_network(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == ((DF_INFRA_DOCKER_NETWORK,), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_compose_prefix_kept_when_confirmed(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    original_prefix = "dfabcdef_"
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.side_effect = [False, True]
    mock_read.return_value = {"df_infra_compose_prefix": original_prefix}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_INFRA_COMPOSE_PREFIX"] == original_prefix


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_compose_prefix_regenerated_when_not_confirmed(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    original_prefix = "dfabcdef_"
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.side_effect = [False, False]
    mock_read.return_value = {"df_infra_compose_prefix": original_prefix}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    new_prefix = infra_values["DF_INFRA_COMPOSE_PREFIX"]
    assert new_prefix != original_prefix
    assert re.match(r"^df[a-z0-9]{6}_$", new_prefix)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_compose_prefix_generated_when_no_original(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert re.match(r"^df[a-z0-9]{6}_$", infra_values["DF_INFRA_COMPOSE_PREFIX"])


@mock.patch("deepfellow.infra.utils.install.echo")
def test_resolve_skips_storage_prompt_when_stored_value_equals_default(
    mock_echo: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    mock_echo.confirm.return_value = True
    context = InstallContext(
        directory=directory,
        docker_socket="/var/run/docker.sock",
        newest_image_tag=None,
        original_env_content={"df_infra_storage_dir": str(DF_INFRA_STORAGE_DIR)},
    )
    kwargs = dict(default_install_kwargs)
    del kwargs["directory"]
    del kwargs["force_install"]
    del kwargs["allow_rootful"]

    config = resolve(context, **kwargs)

    assert config.storage_dir == DF_INFRA_STORAGE_DIR
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call("Is it safe to print API keys here?", from_args=None)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_storage_kept_when_confirmed(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    original_storage = Path("/custom/storage")
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.side_effect = [False, True]
    mock_read.return_value = {"df_infra_storage_dir": str(original_storage)}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_INFRA_STORAGE_DIR"] == original_storage.expanduser().resolve().as_posix()


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_storage_uses_default_when_no_original(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_INFRA_STORAGE_DIR"] == DF_INFRA_STORAGE_DIR.expanduser().resolve().as_posix()


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_metrics_kept_when_confirmed(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, "", ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.side_effect = [False, True]
    mock_read.return_value = {"df_metrics_username": "orig_user", "df_metrics_password": "orig_pass"}

    install(**default_install_kwargs)

    assert mock_gen_password.call_count == 0
    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_METRICS_USERNAME"] == "orig_user"
    assert infra_values["DF_METRICS_PASSWORD"] == "orig_pass"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_metrics_generated_when_not_present(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    mock_gen_password.side_effect = ["gen_user", "gen_pass"]

    install(**default_install_kwargs)

    assert mock_gen_password.call_count == 2
    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_METRICS_USERNAME"] == "gen_user"
    assert infra_values["DF_METRICS_PASSWORD"] == "gen_pass"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_save_env_file(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_save_env.call_count == 1
    assert mock_save_env.call_args == ((directory / ".env", mock.ANY), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_env_set_for_config_file(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    config_file = state.cli_config_file

    install(**default_install_kwargs)

    assert (
        mock.call(
            config_file,
            "DF_INFRA_EXTERNAL_URL",
            f"http://localhost:{DF_INFRA_PORT}",
            should_raise=False,
        )
        in mock_env_set.call_args_list
    )


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_env_set_for_secrets_file(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    mock_configure_uuid.return_value = "test-admin-key"
    secrets_file = state.cli_secrets_file

    install(**default_install_kwargs)

    assert (
        mock.call(
            secrets_file,
            "DF_INFRA_ADMIN_API_KEY",
            "test-admin-key",
            should_raise=False,
        )
        in mock_env_set.call_args_list
    )


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_add_network_to_service(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_add_network.call_count == 1
    assert mock_add_network.call_args == ((mock.ANY, DF_INFRA_DOCKER_NETWORK), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_appends_docker_socket_volumes(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    mock_get_socket.return_value = "/var/run/docker.sock"

    install(**default_install_kwargs)

    compose_arg = mock_save_compose.call_args[0][0]
    volumes = compose_arg["services"]["infra"]["volumes"]
    assert "/var/run/docker.sock:/run/docker.sock" in volumes
    assert "/var/run/docker.sock:/var/run/docker.sock" in volumes
    assert "${DF_INFRA_STORAGE_DIR}:${DF_INFRA_STORAGE_DIR}" in volumes


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_local_image_sets_pull_policy_never(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "local_image": True})

    compose_arg = mock_save_compose.call_args[0][0]
    assert compose_arg["services"]["infra"]["pull_policy"] == "never"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_no_local_image_does_not_set_pull_policy(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    compose_arg = mock_save_compose.call_args[0][0]
    assert "pull_policy" not in compose_arg["services"]["infra"]


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_save_compose_file(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_save_compose.call_count == 1
    assert mock_save_compose.call_args == ((mock.ANY, directory / DOCKER_COMPOSE_CONFIG_FILENAME), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_docker_compose_pull(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
    directory: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "pull"], directory, raises=DockerError)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_calls_echo_success(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    assert mock_echo.success.call_count == 1


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_hugging_face_token_added_to_env_when_provided(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.return_value = False
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "hugging_face_token": "hf-test-token"})

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_HUGGING_FACE_TOKEN"] == "hf-test-token"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_hugging_face_token_not_added_when_empty(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert "DF_HUGGING_FACE_TOKEN" not in infra_values


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_civitai_token_added_to_env_when_provided(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_echo.prompt.side_effect = [DF_INFRA_NAME, DF_INFRA_DOCKER_NETWORK, ""]
    mock_echo.prompt_until_valid.return_value = DF_INFRA_URL
    mock_echo.confirm.return_value = False
    mock_read.return_value = {}

    install(**{**default_install_kwargs, "civitai_token": "civitai-test-token"})

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_CIVITAI_TOKEN"] == "civitai-test-token"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_civitai_token_not_added_when_empty(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(**default_install_kwargs)

    infra_values = mock_save_env.call_args[0][1]
    assert "DF_CIVITAI_TOKEN" not in infra_values


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_delegates_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(**default_install_kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**default_install_kwargs)


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_translates_install_error_to_exit(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(**default_install_kwargs)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_forwards_explicit_confirm_flags_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(
        **{
            **default_install_kwargs,
            "allow_print_keys": True,
            "keep_compose_prefix": False,
            "keep_storage": True,
            "keep_metrics": False,
        }
    )

    assert mock_install_util.call_count == 1
    call_kwargs = mock_install_util.call_args.kwargs
    assert call_kwargs["allow_print_keys"] is True
    assert call_kwargs["keep_compose_prefix"] is False
    assert call_kwargs["keep_storage"] is True
    assert call_kwargs["keep_metrics"] is False


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_util_translates_bad_parameter_to_install_error(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    default_install_kwargs: dict,
) -> None:
    """A caller outside Click (e.g. a future in-process suite install) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter."""
    mock_echo.prompt.side_effect = typer.BadParameter("Invalid DF_NAME - cannot be empty")
    mock_read.return_value = {}

    with pytest.raises(InstallError, match="Invalid DF_NAME - cannot be empty"):
        install(**default_install_kwargs)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_defaults_resolve_to_real_values_when_arguments_omitted(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_get_newest_image_tag: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    tmp_path: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}
    mock_get_newest_image_tag.return_value = "deepfellow/infra:1.2.3"
    mock_gen_password.return_value = "generated-password"

    install(directory=tmp_path)

    name_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == DF_INFRA_NAME
    url_prompt_kwargs = mock_echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == DF_INFRA_URL
    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == DF_INFRA_PORT
    assert infra_values["DF_INFRA_IMAGE"] == "deepfellow/infra:1.2.3"
    assert not any(isinstance(value, OptionInfo) for value in infra_values.values())


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.generate_password")
@mock.patch("deepfellow.infra.utils.install.configure_uuid_key")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_install_passes_explicit_values_to_prompts_as_from_args(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_dir: Mock,
    mock_read: Mock,
    mock_configure_uuid: Mock,
    mock_gen_password: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    tmp_path: Path,
) -> None:
    _setup_echo(mock_echo)
    mock_read.return_value = {}

    install(
        directory=tmp_path,
        image="custom:image",
        local_image=True,
        infra_name="custom-name",
        infra_url="https://custom.example.com",
        docker_network="custom-net",
    )

    name_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == "custom-name"
    url_prompt_kwargs = mock_echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == "https://custom.example.com"
    network_prompt_kwargs = mock_echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["from_args"] == "custom-net"


# apply() is purely programmatic (network, .env, compose, pull) - no prompts, so none of these
# tests mock echo.prompt/echo.confirm.


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_creates_docker_config_when_not_a_file(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
    docker_config: Mock,
) -> None:
    docker_config.is_file.return_value = False

    apply(install_config)

    assert docker_config.write_text.call_count == 1
    assert docker_config.write_text.call_args == (("{}",), {"encoding": "utf-8"})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_raises_exit_when_docker_config_write_fails(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
    docker_config: Mock,
) -> None:
    docker_config.is_file.return_value = False
    docker_config.write_text.side_effect = OSError("disk full")

    with pytest.raises(typer.Exit):
        apply(install_config)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("disk full")
    assert mock_ensure_network.call_count == 0
    assert mock_save_env.call_count == 0


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_does_not_create_docker_config_when_file_exists(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
    docker_config: Mock,
) -> None:
    docker_config.is_file.return_value = True

    apply(install_config)

    assert docker_config.write_text.call_count == 0


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_calls_ensure_network_with_configured_docker_network(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == ((install_config.docker_network,), {})


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_writes_expected_env_values(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_save_env.call_count == 1
    env_file, infra_values = mock_save_env.call_args[0]
    assert env_file == install_config.directory / ".env"
    assert infra_values["DF_NAME"] == install_config.df_name
    assert infra_values["DF_INFRA_URL"] == install_config.infra_url
    assert infra_values["DF_INFRA_PORT"] == install_config.infra_port
    assert infra_values["DF_INFRA_IMAGE"] == install_config.df_infra_image
    assert infra_values["DF_MESH_KEY"] == install_config.mesh_key
    assert infra_values["DF_INFRA_API_KEY"] == install_config.api_key
    assert infra_values["DF_INFRA_ADMIN_API_KEY"] == install_config.admin_api_key
    assert infra_values["DF_CONNECT_TO_MESH_URL"] == ""
    assert infra_values["DF_CONNECT_TO_MESH_KEY"] == ""
    assert infra_values["DF_INFRA_DOCKER_SUBNET"] == install_config.docker_network
    assert infra_values["DF_INFRA_COMPOSE_PREFIX"] == install_config.compose_prefix
    assert infra_values["DF_INFRA_DOCKER_CONFIG"] == str(install_config.docker_config)
    assert infra_values["DF_INFRA_STORAGE_DIR"] == install_config.storage_dir.expanduser().resolve().as_posix()
    assert infra_values["DF_METRICS_USERNAME"] == install_config.metrics_username
    assert infra_values["DF_METRICS_PASSWORD"] == install_config.metrics_password
    assert "DF_HUGGING_FACE_TOKEN" not in infra_values
    assert "DF_CIVITAI_TOKEN" not in infra_values


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_includes_optional_tokens_when_present(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.hugging_face_token = "hf-token"
    install_config.civitai_token = "civitai-token"

    apply(install_config)

    infra_values = mock_save_env.call_args[0][1]
    assert infra_values["DF_HUGGING_FACE_TOKEN"] == "hf-token"
    assert infra_values["DF_CIVITAI_TOKEN"] == "civitai-token"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_sets_external_url_and_admin_api_key(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_env_set.call_count == 2
    assert mock_env_set.call_args_list[0] == mock.call(
        state.cli_config_file,
        "DF_INFRA_EXTERNAL_URL",
        f"http://localhost:{install_config.infra_port}",
        should_raise=False,
    )
    assert mock_env_set.call_args_list[1] == mock.call(
        state.cli_secrets_file,
        "DF_INFRA_ADMIN_API_KEY",
        install_config.admin_api_key,
        should_raise=False,
    )


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_adds_docker_socket_volumes_to_compose(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_save_compose.call_count == 1
    compose_dict, compose_file = mock_save_compose.call_args[0]
    volumes = compose_dict["services"]["infra"]["volumes"]
    assert f"{install_config.docker_socket}:/run/docker.sock" in volumes
    assert f"{install_config.docker_socket}:/var/run/docker.sock" in volumes
    assert compose_dict["networks"] == {install_config.docker_network: {"external": True}}
    assert compose_file == install_config.directory / DOCKER_COMPOSE_CONFIG_FILENAME


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_sets_pull_policy_never_when_local_image(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.local_image = True

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert compose_dict["services"]["infra"]["pull_policy"] == "never"


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_does_not_set_pull_policy_when_not_local_image(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.local_image = False

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "pull_policy" not in compose_dict["services"]["infra"]


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_pulls_docker_image(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "pull"], install_config.directory, raises=DockerError)


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_raises_exit_when_docker_compose_pull_fails(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    mock_run.side_effect = DockerError("pull access denied")

    with pytest.raises(typer.Exit):
        apply(install_config)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Failed to pull docker image(s): pull access denied\nCheck registry access, credentials, and disk space."
    )
    assert mock_echo.success.call_count == 0


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_prints_success_message(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_echo.success.call_count == 1
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.confirm.call_count == 0
