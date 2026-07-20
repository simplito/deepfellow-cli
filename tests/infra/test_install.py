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
from deepfellow.common.state import state
from deepfellow.infra.install import install as install_command
from deepfellow.infra.utils.install import install


@pytest.fixture
def docker_config() -> Mock:
    m = Mock(spec=Path)
    m.is_file.return_value = True
    return m


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
    assert mock_run.call_args == ((["docker", "compose", "pull"], directory), {"quiet": True})


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
