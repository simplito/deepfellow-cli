# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import inspect
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from click.core import ParameterSource
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
from deepfellow.common.exceptions import DockerNetworkError, InstallError
from deepfellow.common.state import state
from deepfellow.infra.install import install as install_command
from deepfellow.infra.utils.install import InstallConfig, InstallContext, apply, install, mergeable_field_names, resolve
from deepfellow.infra.utils.install import inspect as inspect_util
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES


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
        "template": None,
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


def dummy_ctx() -> Mock:
    """A `typer.Context` stand-in for direct (non-Click) calls to `install_command()`.

    `get_parameter_source()` defaults to DEFAULT for every field, i.e. "nothing was explicitly
    passed" - matching a bare Python call, which has no real Click parsing behind it.
    """
    ctx = mock.MagicMock(spec=typer.Context)
    ctx.get_parameter_source.return_value = ParameterSource.DEFAULT
    return ctx


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

    inspect_util(directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False)

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

    inspect_util(directory=directory, allow_rootful=True, force_install=False, image=DF_INFRA_IMAGE, local_image=False)

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

    inspect_util(directory=directory, allow_rootful=False, force_install=True, image=DF_INFRA_IMAGE, local_image=False)

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

    context = inspect_util(
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

    context = inspect_util(
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

    context = inspect_util(
        directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False
    )

    assert context.directory == directory
    assert context.docker_socket == "/var/run/docker.sock"
    assert context.original_env_content == {"DF_NAME": "infra"}


@mock.patch("deepfellow.infra.utils.install.resolve_template")
@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_resolves_template_before_docker_and_directory_access(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    mock_resolve_template: Mock,
    directory: Path,
) -> None:
    # Regression test for the fail-fast design intent: a bad --template must be caught before any
    # Docker/filesystem side effect, so resolve_template() has to run first.
    call_order: list[str] = []

    def _record_resolve_template(value: str) -> dict[str, Any]:
        call_order.append("resolve_template")
        return {"config": {}, "post_start_actions": []}

    def _record_assert_docker() -> None:
        call_order.append("assert_docker")

    def _record_get_socket(**kwargs: Any) -> str:
        call_order.append("get_socket")
        return "/var/run/docker.sock"

    def _record_ensure_directory(*args: Any, **kwargs: Any) -> None:
        call_order.append("ensure_directory")

    mock_resolve_template.side_effect = _record_resolve_template
    mock_assert_docker.side_effect = _record_assert_docker
    mock_get_socket.side_effect = _record_get_socket
    mock_ensure_directory.side_effect = _record_ensure_directory
    mock_read_env_file_to_dict.return_value = {}

    inspect_util(
        directory=directory,
        allow_rootful=False,
        force_install=False,
        image=DF_INFRA_IMAGE,
        local_image=False,
        template="workspace",
    )

    assert call_order == ["resolve_template", "assert_docker", "get_socket", "ensure_directory"]


@mock.patch("deepfellow.infra.utils.install.resolve_template")
@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_short_circuits_before_docker_when_template_resolution_fails(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    mock_resolve_template: Mock,
    directory: Path,
) -> None:
    mock_resolve_template.side_effect = InstallError("bad template")

    with pytest.raises(InstallError):
        inspect_util(
            directory=directory,
            allow_rootful=False,
            force_install=False,
            image=DF_INFRA_IMAGE,
            local_image=False,
            template="not-a-template",
        )

    assert mock_assert_docker.call_count == 0
    assert mock_get_socket.call_count == 0
    assert mock_ensure_directory.call_count == 0
    assert mock_get_newest_image_tag.call_count == 0
    assert mock_read_env_file_to_dict.call_count == 0


@mock.patch("deepfellow.infra.utils.install.resolve_template")
@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_returns_the_resolved_template_in_context(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    mock_resolve_template: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}
    resolved = {"config": {"port": 9000}, "post_start_actions": []}
    mock_resolve_template.return_value = resolved

    context = inspect_util(
        directory=directory,
        allow_rootful=False,
        force_install=False,
        image=DF_INFRA_IMAGE,
        local_image=False,
        template="workspace",
    )

    assert context.resolved_template == resolved


@mock.patch("deepfellow.infra.utils.install.get_newest_image_tag")
@mock.patch("deepfellow.infra.utils.install.read_env_file_to_dict")
@mock.patch("deepfellow.infra.utils.install.ensure_directory")
@mock.patch("deepfellow.infra.utils.install.get_socket")
@mock.patch("deepfellow.infra.utils.install.assert_docker")
def test_inspect_returns_none_resolved_template_when_no_template_given(
    mock_assert_docker: Mock,
    mock_get_socket: Mock,
    mock_ensure_directory: Mock,
    mock_read_env_file_to_dict: Mock,
    mock_get_newest_image_tag: Mock,
    directory: Path,
) -> None:
    mock_get_socket.return_value = "/var/run/docker.sock"
    mock_read_env_file_to_dict.return_value = {}

    context = inspect_util(
        directory=directory, allow_rootful=False, force_install=False, image=DF_INFRA_IMAGE, local_image=False
    )

    assert context.resolved_template is None


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
def test_install_accepts_builtin_workspace_template_config_without_crashing(
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
    directory: Path,
    docker_config: Mock,
) -> None:
    """Regression test for BUILTIN_TEMPLATES["workspace"]["config"] (infra): every splatted value
    (port, infra_name, infra_url, docker_network) must flow through install() into the saved env
    file unchanged, not just reach the end of install() without raising."""
    mock_echo.prompt.side_effect = lambda *args, **kwargs: kwargs.get("from_args")
    mock_echo.prompt_until_valid.side_effect = lambda *args, **kwargs: kwargs.get("from_args")
    mock_echo.confirm.return_value = False
    mock_read.return_value = {}
    template_config = BUILTIN_TEMPLATES["workspace"]["config"]

    install(
        directory=directory,
        docker_config=docker_config,
        force_install=True,
        **template_config,
    )

    assert mock_save_env.call_count == 1
    saved_env = mock_save_env.call_args[0][1]
    assert saved_env["DF_NAME"] == template_config["infra_name"]
    assert saved_env["DF_INFRA_URL"] == template_config["infra_url"]
    assert saved_env["DF_INFRA_PORT"] == template_config["port"]
    assert saved_env["DF_INFRA_DOCKER_SUBNET"] == template_config["docker_network"]


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
        resolved_template=None,
        directory=directory,
        docker_socket="/var/run/docker.sock",
        newest_image_tag=None,
        original_env_content={"df_infra_storage_dir": str(DF_INFRA_STORAGE_DIR)},
    )
    kwargs = dict(default_install_kwargs)
    del kwargs["directory"]
    del kwargs["force_install"]
    del kwargs["allow_rootful"]
    del kwargs["template"]

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
    install_command(ctx=dummy_ctx(), **default_install_kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**default_install_kwargs, explicitly_provided=set())
    assert set(mock_install_util.call_args[1]) == set(inspect.signature(install).parameters)


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_computes_explicitly_provided_from_parameter_source(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    """explicitly_provided must reflect ctx.get_parameter_source(), not merely be an empty set -
    COMMANDLINE and ENVIRONMENT both count as explicit, DEFAULT doesn't."""
    ctx = dummy_ctx()
    ctx.get_parameter_source.side_effect = lambda name: {
        "port": ParameterSource.COMMANDLINE,
        "infra_url": ParameterSource.ENVIRONMENT,
    }.get(name, ParameterSource.DEFAULT)

    install_command(ctx=ctx, **default_install_kwargs)

    assert mock_install_util.call_args[1]["explicitly_provided"] == {"port", "infra_url"}


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_translates_install_error_to_exit(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(ctx=dummy_ctx(), **default_install_kwargs)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.infra.install.install_util")
def test_install_command_forwards_explicit_confirm_flags_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(
        ctx=dummy_ctx(),
        **{
            **default_install_kwargs,
            "allow_print_keys": True,
            "keep_compose_prefix": False,
            "keep_storage": True,
            "keep_metrics": False,
        },
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


def test_install_command_signature_matches_install_util():
    """The command's own CLI-facing params must exactly match the util function's, in the same
    order - `ctx` (Typer-only, used for explicitness detection) and `explicitly_provided`
    (util-only, computed by the command from `ctx`) are the sole, deliberate exceptions."""
    command_params = list(inspect.signature(install_command).parameters)
    util_params = list(inspect.signature(install).parameters)

    assert command_params[0] == "ctx"
    assert util_params[-1] == "explicitly_provided"
    assert command_params[1:] == util_params[:-1]


def test_mergeable_field_names_are_real_command_parameters():
    """Every `mergeable_field_names()` key must name an actual parameter of the Typer command -
    `ctx.get_parameter_source(key)` silently returns None for an unknown name, which the command
    then treats as "not explicitly provided", so a key/parameter-name drift (e.g. a future rename)
    would silently reinstate the exact precedence bug this module exists to fix, with no error and
    no other test catching it."""
    assert mergeable_field_names() <= set(inspect.signature(install_command).parameters)


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


@dataclass
class InstallMocks:
    """Bundles every mock.patch target install()'s full flow touches.

    Replaces the 13-16 individual @mock.patch decorators (one per dependency) that install()-level
    tests below would otherwise repeat near-verbatim; use the `install_mocks` fixture to get one.
    """

    echo: Mock
    assert_docker: Mock
    get_socket: Mock
    ensure_directory: Mock
    read_env_file_to_dict: Mock
    configure_uuid_key: Mock
    generate_password: Mock
    env_set: Mock
    save_env_file: Mock
    ensure_network: Mock
    add_network_to_service: Mock
    save_compose_file: Mock
    run: Mock
    resolve_template: Mock
    start_infra: Mock
    dispatch_post_start_action: Mock
    get_newest_image_tag: Mock


@pytest.fixture
def install_mocks() -> Iterator[InstallMocks]:
    """Patch every dependency deepfellow.infra.utils.install.install() touches, as one bundle."""
    targets = {
        "echo": "deepfellow.infra.utils.install.echo",
        "assert_docker": "deepfellow.infra.utils.install.assert_docker",
        "get_socket": "deepfellow.infra.utils.install.get_socket",
        "ensure_directory": "deepfellow.infra.utils.install.ensure_directory",
        "read_env_file_to_dict": "deepfellow.infra.utils.install.read_env_file_to_dict",
        "configure_uuid_key": "deepfellow.infra.utils.install.configure_uuid_key",
        "generate_password": "deepfellow.infra.utils.install.generate_password",
        "env_set": "deepfellow.infra.utils.install.env_set",
        "save_env_file": "deepfellow.infra.utils.install.save_env_file",
        "ensure_network": "deepfellow.infra.utils.install.ensure_network",
        "add_network_to_service": "deepfellow.infra.utils.install.add_network_to_service",
        "save_compose_file": "deepfellow.infra.utils.install.save_compose_file",
        "run": "deepfellow.infra.utils.install.run",
        "resolve_template": "deepfellow.infra.utils.install.resolve_template",
        "start_infra": "deepfellow.infra.utils.install.start_infra",
        "dispatch_post_start_action": "deepfellow.infra.utils.install.dispatch_post_start_action",
        "get_newest_image_tag": "deepfellow.infra.utils.install.get_newest_image_tag",
    }
    patchers = {name: mock.patch(target) for name, target in targets.items()}
    started = {name: patcher.start() for name, patcher in patchers.items()}
    # Default to "no newer tag found" so tests stay hermetic - without this, a MagicMock (always
    # truthy) would win over `image` in `context.newest_image_tag or image` in resolve().
    started["get_newest_image_tag"].return_value = None
    yield InstallMocks(**started)
    for patcher in patchers.values():
        patcher.stop()


def test_install_resolves_template_when_given(install_mocks: InstallMocks, tmp_path: Path) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {"config": {}, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    assert install_mocks.resolve_template.call_count == 1
    assert install_mocks.resolve_template.call_args == mock.call("workspace")


def test_install_skips_template_resolution_when_not_given(install_mocks: InstallMocks, tmp_path: Path) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}

    install(directory=tmp_path)

    assert install_mocks.resolve_template.call_count == 0


def test_install_force_provided_is_false_for_all_fields_when_no_template_given(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: force_provided exists specifically to skip re-prompting for a
    # template-sourced value - it must stay False when there's no template at all.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}

    install(directory=tmp_path)

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["force_provided"] is False
    url_prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["force_provided"] is False
    network_prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["force_provided"] is False


def test_install_merges_template_config_when_cli_args_are_still_default(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    template_config = {
        "port": 9999,
        "infra_name": "templated-infra",
        "infra_url": "http://templated:9999",
        "docker_network": "templated-net",
    }
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == template_config["infra_name"]
    assert name_prompt_kwargs["force_provided"] is True
    url_prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == template_config["infra_url"]
    assert url_prompt_kwargs["force_provided"] is True
    network_prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["from_args"] == template_config["docker_network"]
    assert network_prompt_kwargs["force_provided"] is True
    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == template_config["port"]


def test_install_preserves_prior_env_value_over_template_config(install_mocks: InstallMocks, tmp_path: Path) -> None:
    # Regression test: a template must not silently discard a value a prior install already
    # configured in .env, even when the CLI arg for that field is still at its own default.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_name": "existing-name"}
    template_config = {"infra_name": "templated-infra"}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == DF_INFRA_NAME
    assert name_prompt_kwargs["force_provided"] is False
    assert name_prompt_kwargs["default"] == "existing-name"


@mock.patch("deepfellow.infra.utils.install.read_config_json_settings")
def test_install_preserves_prior_config_json_value_over_template_config(
    mock_read_config_json_settings: Mock, install_mocks: InstallMocks, tmp_path: Path
) -> None:
    """Regression test for DFCLI-55: a template must not silently discard a value that only exists
    in config.json - e.g. a field that migrated away from .env after the service's first start, so
    .env alone would see it as "unset"."""
    _setup_echo(install_mocks.echo)
    (tmp_path / ".env").touch()  # config.json is only consulted once a prior .env is confirmed
    install_mocks.read_env_file_to_dict.return_value = {}
    mock_read_config_json_settings.return_value = {"name": "existing-name"}
    template_config = {"infra_name": "templated-infra"}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == DF_INFRA_NAME
    assert name_prompt_kwargs["force_provided"] is False
    assert name_prompt_kwargs["default"] == "existing-name"


def test_install_preserves_prior_env_infra_url_over_template_config(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Isolated per-field regression test, mirroring the infra_name one above: a typo in
    # infra_url's own env_key ("df_infra_url") would go undetected without this.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_url": "http://existing:8086"}
    template_config = {"infra_url": "http://templated:9999"}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    url_prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == DF_INFRA_URL
    assert url_prompt_kwargs["force_provided"] is False
    assert url_prompt_kwargs["default"] == "http://existing:8086"


def test_install_preserves_prior_env_docker_network_over_template_config(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Isolated per-field regression test, mirroring the infra_name one above: a typo in
    # docker_network's own env_key ("df_infra_docker_subnet") would go undetected without this.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_docker_subnet": "existing-net"}
    template_config = {"docker_network": "templated-net"}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    network_prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["from_args"] == DF_INFRA_DOCKER_NETWORK
    assert network_prompt_kwargs["force_provided"] is False
    assert network_prompt_kwargs["default"] == "existing-net"


def test_install_does_not_apply_template_port_when_a_prior_env_port_exists(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: a template must not silently pick a DIFFERENT port than a prior install's
    # .env - same protection infra_name/infra_url/docker_network already get. Unlike those three,
    # port has no "keep previous value" prompt of its own, so _resolve_port() restores the
    # prior port (9500 here) itself; otherwise the CLI's own default would silently overwrite it
    # when .env is saved.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_port": "9500"}
    template_config = {"port": 9999}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 9500


def test_install_restores_prior_port_when_no_template_given(install_mocks: InstallMocks, tmp_path: Path) -> None:
    # Regression test: _resolve_port() must restore a prior install's port unconditionally, not
    # only when a --template happens to also declare "port" - _merge_template_config()'s per-key
    # loop is gated on `key in template_config`, which a plain `infra install` re-run (no template
    # at all) never satisfies, so restoration must not depend on reaching that loop.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_port": "9500"}

    install(directory=tmp_path)

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 9500


def test_install_restores_prior_port_when_template_omits_port(install_mocks: InstallMocks, tmp_path: Path) -> None:
    # Same regression as above, for a --template that simply doesn't declare "port" at all.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_port": "9500"}
    install_mocks.resolve_template.return_value = {
        "config": {"docker_network": "templated-net"},
        "post_start_actions": [],
    }

    install(directory=tmp_path, template="workspace")

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 9500


def test_install_explicit_port_wins_over_prior_env_port(install_mocks: InstallMocks, tmp_path: Path) -> None:
    # Regression test: an explicit --port must win over a prior install's .env port. The other
    # prior-port tests never mark "port" as explicit, and the explicit-port tests never seed a
    # prior .env port, so neither would catch _resolve_port()'s explicitly_provided check being
    # skipped (or checked too late) whenever a prior .env value happens to be present.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_port": "9500"}

    install(directory=tmp_path, port=1111, explicitly_provided={"port"})

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 1111


def test_install_raises_install_error_when_prior_env_port_is_not_numeric(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: a hand-edited .env with a non-numeric DF_INFRA_PORT must surface as a
    # message-carrying InstallError, not an unhandled ValueError from int(str(prior_value)).
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {"df_infra_port": "not-a-port"}
    install_mocks.resolve_template.return_value = {"config": {"port": 9999}, "post_start_actions": []}

    with pytest.raises(InstallError, match="DF_INFRA_PORT"):
        install(directory=tmp_path, template="workspace")


@pytest.mark.parametrize(
    ("env_key", "field"),
    [("df_name", "infra_name"), ("df_infra_url", "infra_url"), ("df_infra_docker_subnet", "docker_network")],
)
def test_install_applies_template_config_when_prior_env_value_is_empty_string(
    install_mocks: InstallMocks, env_key: str, field: str, tmp_path: Path
) -> None:
    # Regression test: an empty string in a prior .env (e.g. "DF_INFRA_URL=") must be treated like
    # no prior value at all, not like an explicit one - otherwise it silently blocks the template's
    # value the same way a real prior value legitimately would.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {env_key: ""}
    template_config = {field: "templated-value"}
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    if field == "infra_name":
        prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    elif field == "infra_url":
        prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    else:
        prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert prompt_kwargs["from_args"] == "templated-value"
    assert prompt_kwargs["force_provided"] is True


def test_install_explicit_cli_arg_wins_over_template_config(install_mocks: InstallMocks, tmp_path: Path) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    template_config = {
        "port": 9999,
        "infra_name": "templated-infra",
        "infra_url": "http://templated:9999",
        "docker_network": "templated-net",
    }
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(
        directory=tmp_path,
        template="workspace",
        infra_name="explicit-name",
        port=1234,
        explicitly_provided={"infra_name", "port"},
    )

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == "explicit-name"
    assert name_prompt_kwargs["force_provided"] is False
    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 1234


def test_install_explicit_cli_arg_equal_to_its_own_default_wins_over_template_config(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: the old `merged[key] != own_default` heuristic couldn't tell an explicit
    # flag that happens to equal its own default from one never passed at all - and the built-in
    # "workspace" template's config *is* the CLI defaults, so this is the ordinary case here, not a
    # corner case. Every field below is explicit and equal to its own default; the template sets a
    # DIFFERENT value for each, so only explicitly_provided (not a value comparison) can make the
    # explicit flag win. This test fails under the old heuristic for all four fields at once.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    template_config = {
        "port": 9999,
        "infra_name": "templated-infra",
        "infra_url": "http://templated:9999",
        "docker_network": "templated-net",
    }
    install_mocks.resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(
        directory=tmp_path,
        template="workspace",
        port=DF_INFRA_PORT,
        infra_name=DF_INFRA_NAME,
        infra_url=DF_INFRA_URL,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        explicitly_provided={"port", "infra_name", "infra_url", "docker_network"},
    )

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == DF_INFRA_NAME
    assert name_prompt_kwargs["force_provided"] is False
    url_prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == DF_INFRA_URL
    assert url_prompt_kwargs["force_provided"] is False
    network_prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["from_args"] == DF_INFRA_DOCKER_NETWORK
    assert network_prompt_kwargs["force_provided"] is False
    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == DF_INFRA_PORT


# Regression coverage for _merge_template_config's shared loop over _MERGEABLE_FIELDS: the two
# tests above set ALL fields explicit or ALL at default, which can't tell the loop's per-field
# handling apart - every field's condition is true/false together in those cases. Isolating
# exactly one explicit field per case below means a _MERGEABLE_FIELDS entry wired to the wrong
# field's default/env_key (e.g. a mis-ordered tuple, or infra_url's entry using infra_name's
# default by mistake) shows up as a wrong merged value.
_TEMPLATE_CONFIG_FOR_ISOLATION_TEST: dict[str, Any] = {
    "port": 9999,
    "infra_name": "templated-infra",
    "infra_url": "http://templated:9999",
    "docker_network": "templated-net",
}
_EXPLICIT_VALUE_FOR_ISOLATION_TEST: dict[str, Any] = {
    "port": 1234,
    "infra_name": "explicit-name",
    "infra_url": "http://explicit:1234",
    "docker_network": "explicit-net",
}


@pytest.mark.parametrize("explicit_field", ["port", "infra_name", "infra_url", "docker_network"])
def test_install_only_the_explicit_field_wins_the_other_three_still_use_template(
    install_mocks: InstallMocks, explicit_field: str, tmp_path: Path
) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {
        "config": dict(_TEMPLATE_CONFIG_FOR_ISOLATION_TEST),
        "post_start_actions": [],
    }

    install(
        directory=tmp_path,
        template="workspace",
        port=_EXPLICIT_VALUE_FOR_ISOLATION_TEST["port"] if explicit_field == "port" else DF_INFRA_PORT,
        infra_name=(
            _EXPLICIT_VALUE_FOR_ISOLATION_TEST["infra_name"] if explicit_field == "infra_name" else DF_INFRA_NAME
        ),
        infra_url=(_EXPLICIT_VALUE_FOR_ISOLATION_TEST["infra_url"] if explicit_field == "infra_url" else DF_INFRA_URL),
        docker_network=(
            _EXPLICIT_VALUE_FOR_ISOLATION_TEST["docker_network"]
            if explicit_field == "docker_network"
            else DF_INFRA_DOCKER_NETWORK
        ),
        explicitly_provided={explicit_field},
    )

    expected = {
        key: (
            _EXPLICIT_VALUE_FOR_ISOLATION_TEST[key]
            if key == explicit_field
            else _TEMPLATE_CONFIG_FOR_ISOLATION_TEST[key]
        )
        for key in _TEMPLATE_CONFIG_FOR_ISOLATION_TEST
    }

    name_prompt_kwargs = install_mocks.echo.prompt.call_args_list[0][1]
    assert name_prompt_kwargs["from_args"] == expected["infra_name"]
    assert name_prompt_kwargs["force_provided"] is (explicit_field != "infra_name")

    url_prompt_kwargs = install_mocks.echo.prompt_until_valid.call_args[1]
    assert url_prompt_kwargs["from_args"] == expected["infra_url"]
    assert url_prompt_kwargs["force_provided"] is (explicit_field != "infra_url")

    network_prompt_kwargs = install_mocks.echo.prompt.call_args_list[1][1]
    assert network_prompt_kwargs["from_args"] == expected["docker_network"]
    assert network_prompt_kwargs["force_provided"] is (explicit_field != "docker_network")

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == expected["port"]


def test_install_starts_infra_and_dispatches_post_start_actions_in_order(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    actions: list[dict[str, Any]] = [
        {"function": "infra.service.install", "kwargs": {"name": "ollama"}},
        {"function": "infra.model.install", "kwargs": {"service_name": "ollama", "model_name": "gemma4:e4b"}},
    ]
    install_mocks.resolve_template.return_value = {"config": {}, "post_start_actions": actions}

    install(directory=tmp_path, template="workspace")

    assert install_mocks.start_infra.call_count == 1
    assert install_mocks.start_infra.call_args == mock.call(tmp_path)
    assert install_mocks.dispatch_post_start_action.call_args_list == [mock.call(actions[0]), mock.call(actions[1])]
    assert actions[0]["kwargs"]["server"] == f"http://localhost:{DF_INFRA_PORT}"
    assert actions[1]["kwargs"]["server"] == f"http://localhost:{DF_INFRA_PORT}"
    assert install_mocks.echo.warning.call_count == 0


def test_install_overwrites_and_warns_about_a_template_supplied_server(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: a template-authored "server" kwarg must still be overridden (post-start
    # actions always target the infra instance actually just installed), but not silently - the
    # user should be told their template's value was replaced.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    action: dict[str, Any] = {
        "function": "infra.service.install",
        "kwargs": {"name": "ollama", "server": "http://custom-host:1234"},
    }
    install_mocks.resolve_template.return_value = {"config": {}, "post_start_actions": [action]}

    install(directory=tmp_path, template="workspace")

    assert action["kwargs"]["server"] == f"http://localhost:{DF_INFRA_PORT}"
    warning_messages = [call.args[0] for call in install_mocks.echo.warning.call_args_list]
    assert (
        "Post-start action 1/1 ('infra.service.install') set its own 'server' "
        f"('http://custom-host:1234'); overriding it with the actually-installed infra's address "
        f"('http://localhost:{DF_INFRA_PORT}')."
    ) in warning_messages


def test_install_injects_server_from_the_actually_resolved_port_not_the_default(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: post-start actions must reach the infra instance actually installed on the
    # explicitly-requested port, not a URL baked from the default DF_INFRA_PORT at import time.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    action: dict[str, Any] = {"function": "infra.service.install", "kwargs": {"name": "ollama"}}
    install_mocks.resolve_template.return_value = {"config": {}, "post_start_actions": [action]}

    install(directory=tmp_path, template="workspace", port=9000)

    assert action["kwargs"]["server"] == "http://localhost:9000"


def test_install_injects_server_from_a_template_sourced_port(install_mocks: InstallMocks, tmp_path: Path) -> None:
    # Regression test combining this PR's two headline features: when the template (not an
    # explicit --port) supplies the port, post-start actions must still target that resolved
    # port, not the default - the merge and the injection have to compose correctly together.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    action: dict[str, Any] = {"function": "infra.service.install", "kwargs": {"name": "ollama"}}
    install_mocks.resolve_template.return_value = {"config": {"port": 9500}, "post_start_actions": [action]}

    install(directory=tmp_path, template="workspace")

    infra_values = install_mocks.save_env_file.call_args[0][1]
    assert infra_values["DF_INFRA_PORT"] == 9500
    assert action["kwargs"]["server"] == "http://localhost:9500"


def test_install_skips_start_infra_when_template_has_no_post_start_actions(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {"config": {"port": 9999}, "post_start_actions": []}

    install(directory=tmp_path, template="workspace")

    assert install_mocks.start_infra.call_count == 0
    assert install_mocks.dispatch_post_start_action.call_count == 0


def test_install_raises_install_error_when_post_start_action_fails(install_mocks: InstallMocks, tmp_path: Path) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {
        "config": {},
        "post_start_actions": [{"function": "infra.model.install", "kwargs": {}}],
    }
    install_mocks.dispatch_post_start_action.side_effect = InstallError("bad kwargs")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace")

    error_messages = [call.args[0] for call in install_mocks.echo.error.call_args_list]
    assert (
        "Post-start action 1/1 ('infra.model.install') failed: bad kwargs\n"
        "Infra is already installed and running; 0 of 1 action(s) completed before this failure."
    ) in error_messages


def test_install_names_the_failing_action_when_the_second_of_three_fails(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    # Regression test: a mid-list failure must name which action failed and how many already
    # completed, not a message identical to every other action's failure. InstallError is the
    # only failure mode dispatch_post_start_action can ever raise here (it's decorated with
    # @translate_to_install_error, which unconditionally converts typer.Exit into InstallError
    # before it escapes) - so that's what's simulated, not typer.Exit.
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    actions = [
        {"function": "infra.service.install", "kwargs": {"name": "ollama"}},
        {"function": "infra.model.install", "kwargs": {"service_name": "ollama", "model_name": "gemma4:e4b"}},
        {"function": "infra.model.install", "kwargs": {"service_name": "ollama", "model_name": "qwen3.5:4b"}},
    ]
    install_mocks.resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    install_mocks.dispatch_post_start_action.side_effect = [None, InstallError("model not found"), None]

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace")

    error_messages = [call.args[0] for call in install_mocks.echo.error.call_args_list]
    assert (
        "Post-start action 2/3 ('infra.model.install') failed: model not found\n"
        "Infra is already installed and running; 1 of 3 action(s) completed before this failure."
    ) in error_messages
    assert install_mocks.dispatch_post_start_action.call_count == 2


def test_install_raises_install_error_when_start_infra_exits(install_mocks: InstallMocks, tmp_path: Path) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {
        "config": {},
        "post_start_actions": [{"function": "infra.model.install", "kwargs": {}}],
    }
    install_mocks.start_infra.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace")

    error_messages = [call.args[0] for call in install_mocks.echo.error.call_args_list]
    assert (
        "Failed to start infra for template post-start actions: see console output above for details."
    ) in error_messages
    assert install_mocks.dispatch_post_start_action.call_count == 0


def test_install_raises_install_error_when_start_infra_hits_a_docker_network_error(
    install_mocks: InstallMocks, tmp_path: Path
) -> None:
    _setup_echo(install_mocks.echo)
    install_mocks.read_env_file_to_dict.return_value = {}
    install_mocks.resolve_template.return_value = {
        "config": {},
        "post_start_actions": [{"function": "infra.model.install", "kwargs": {}}],
    }
    install_mocks.start_infra.side_effect = DockerNetworkError("unable to list networks")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace")

    error_messages = [call.args[0] for call in install_mocks.echo.error.call_args_list]
    assert ("Failed to start infra for template post-start actions: unable to list networks") in error_messages
    assert install_mocks.dispatch_post_start_action.call_count == 0


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
    assert "To start the docker image - `deepfellow infra start`." in mock_echo.success.call_args[0][0]


@mock.patch("deepfellow.infra.utils.install.run")
@mock.patch("deepfellow.infra.utils.install.save_compose_file")
@mock.patch("deepfellow.infra.utils.install.add_network_to_service")
@mock.patch("deepfellow.infra.utils.install.ensure_network")
@mock.patch("deepfellow.infra.utils.install.save_env_file")
@mock.patch("deepfellow.infra.utils.install.env_set")
@mock.patch("deepfellow.infra.utils.install.echo")
def test_apply_success_message_reflects_auto_start_for_templates_with_post_start_actions(
    mock_echo: Mock,
    mock_env_set: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    # Regression test: telling the user to run `infra start` is misleading when install() is
    # about to start infra itself right after, to run the template's post-start actions.
    apply(install_config, will_auto_start=True)

    assert mock_echo.success.call_count == 1
    message = mock_echo.success.call_args[0][0]
    assert "Starting it now to run the template's post-start actions." in message
    assert "deepfellow infra start" not in message
