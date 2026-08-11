# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server install command."""

import inspect
import json
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.models import OptionInfo

from deepfellow.common.config import read_env_file
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_INFRA_DOCKER_NETWORK,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_NEO4J_URI,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_NEO4J,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import DockerError
from deepfellow.common.exceptions import InstallError
from deepfellow.server.install import install as install_command
from deepfellow.server.utils.configure import Neo4jConfig, OtelConfig
from deepfellow.server.utils.install import (
    InstallConfig,
    InstallContext,
    _is_json_object,
    apply,
    expose_ports_to_host,
    install,
    resolve,
)
from deepfellow.server.utils.install import inspect as inspect_util
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES

MOCK_ECHO = mock.patch("deepfellow.server.utils.install.echo")
MOCK_ASSERT_DOCKER = mock.patch("deepfellow.server.utils.install.assert_docker")
MOCK_ENSURE_DIRECTORY = mock.patch("deepfellow.server.utils.install.ensure_directory")
MOCK_ENSURE_NETWORK = mock.patch("deepfellow.server.utils.install.ensure_network")
MOCK_CONFIGURE_MONGO = mock.patch("deepfellow.server.utils.install.configure_mongo")
MOCK_CONFIGURE_INFRA = mock.patch("deepfellow.server.utils.install.configure_infra")
MOCK_CONFIGURE_VECTOR_DB = mock.patch("deepfellow.server.utils.install.configure_vector_db")
MOCK_CONFIGURE_OTEL = mock.patch("deepfellow.server.utils.install.configure_otel")
MOCK_RUN = mock.patch("deepfellow.server.utils.install.run")
MOCK_SAVE_COMPOSE_FILE = mock.patch("deepfellow.server.utils.install.save_compose_file")
MOCK_SAVE_ENV_FILE = mock.patch("deepfellow.server.utils.install.save_env_file")
MOCK_GET_NEWEST_IMAGE_TAG = mock.patch("deepfellow.server.utils.install.get_newest_image_tag")


def install_kwargs(directory: Path) -> dict[str, Any]:
    """Build explicit arguments for calling install() directly, bypassing typer defaults."""
    return {
        "directory": directory,
        "port": 8000,
        "image": "deepfellow-server:test",
        "local_image": False,
        "otel_url": None,
        "otel_local": False,
        "infra_url": "http://infra:8080",
        "infra_api_key": "api-key",
        "docker_network": "deepfellow-network",
        "mongodb_url": "custom-mongo:27017",
        "mongodb_port": 27017,
        "mongodb_database_name": "deepfellow",
        "mongodb_username": "",
        "mongodb_password": "",
        "vectordb_active": False,
        "vectordb_type": VectorDBTypeChoice.qdrant,
        "vectordb_url": "",
        "vectordb_database_name": "",
        "vectordb_username": "",
        "vectordb_password": "",
        "embedding_model": "",
        "embedding_size": "",
        "embedding_sparse": False,
        "neo4j_active": False,
        "neo4j_url": DF_NEO4J_URI,
        "neo4j_username": "",
        "neo4j_password": "",
        "force_install": True,
        "dev": False,
    }


def configure_install_mocks(
    mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
) -> None:
    """Set return values required by the install() happy path."""
    mock_echo.prompt.return_value = "deepfellow-network"
    mock_configure_mongo.return_value = {}
    mock_configure_infra.return_value = {"DF_INFRA__URL": "http://infra:8080", "DF_INFRA__API_KEY": "api-key"}
    mock_configure_vector_db.return_value = (False, {"DF_VECTOR_DATABASE__PROVIDER__ACTIVE": "0"})
    mock_configure_otel.return_value = mock.Mock(envs={}, docker_compose=None)


@MOCK_ENSURE_DIRECTORY
@MOCK_CONFIGURE_OTEL
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_otel_local_and_otel_url_are_mutually_exclusive(
    mock_echo, mock_assert_docker, mock_configure_otel, mock_ensure_directory
):
    with pytest.raises(InstallError):
        install(otel_local=True, otel_url="http://existing-otel:4317")

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--otel-local and --otel-url are mutually exclusive; pass only one.")
    assert mock_assert_docker.call_count == 0
    assert mock_configure_otel.call_count == 0
    assert mock_ensure_directory.call_count == 0


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_writes_log_level_and_plugins_setup_defaults(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(**install_kwargs(tmp_path))

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_LOG_LEVEL"] == "INFO"
    assert env_vars["DF_PLUGINS_SETUP"] == "{}"


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_preserves_existing_log_level_and_plugins_setup(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text('DF_LOG_LEVEL=DEBUG\nDF_PLUGINS_SETUP={"df_anonymize_models": ["model-a"]}\n')

    install(**install_kwargs(tmp_path))

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_LOG_LEVEL"] == "DEBUG"
    assert json.loads(env_vars["DF_PLUGINS_SETUP"]) == {"df_anonymize_models": ["model-a"]}


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_compose_environment_forwards_log_level_and_plugins_setup(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(**install_kwargs(tmp_path))

    assert mock_save_compose_file.call_count == 1
    compose_content = mock_save_compose_file.call_args[0][0]
    environment = compose_content["services"]["server"]["environment"]
    assert "DF_LOG_LEVEL=${DF_LOG_LEVEL}" in environment
    assert "DF_PLUGINS_SETUP=${DF_PLUGINS_SETUP}" in environment


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@mock.patch("deepfellow.server.utils.install.DF_SERVER_STORAGE_DIRECTORY")
@MOCK_ECHO
def test_install_translates_storage_directory_oserror_to_install_error(
    mock_echo,
    mock_storage_directory,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    """A permission error while creating the storage bind-mount directory must surface as a
    clean InstallError (echo.error + reraise_if_debug -> typer.Exit -> InstallError), not an
    unhandled OSError propagating out of install()."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_storage_directory.mkdir.side_effect = OSError("Permission denied")

    with pytest.raises(InstallError):
        install(**install_kwargs(tmp_path))

    assert mock_echo.error.call_count == 1
    assert mock_save_compose_file.call_count == 0


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_rejects_invalid_plugins_setup(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_PLUGINS_SETUP=not-json\n")

    with pytest.raises(InstallError):
        install(**install_kwargs(tmp_path))

    assert mock_echo.error.call_count == 1
    assert mock_save_compose_file.call_count == 0


@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_returns_context_with_defaults_when_no_env_file(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, tmp_path: Path
) -> None:
    context = inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_assert_docker.call_count == 1
    assert context.directory == tmp_path
    assert context.newest_image_tag is None
    assert context.original_env_content == {}
    assert context.log_level == "INFO"
    assert context.plugins_setup == "{}"


@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_preserves_existing_log_level_and_plugins_setup(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text('DF_LOG_LEVEL=DEBUG\nDF_PLUGINS_SETUP={"df_anonymize_models": ["model-a"]}\n')

    context = inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert context.log_level == "DEBUG"
    assert json.loads(context.plugins_setup) == {"df_anonymize_models": ["model-a"]}


@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_rejects_invalid_log_level(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("DF_LOG_LEVEL=NOT_A_LEVEL\n")

    with pytest.raises(typer.Exit):
        inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.error.call_count == 1
    assert "Invalid DF_LOG_LEVEL" in mock_echo.error.call_args[0][0]


@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_rejects_malformed_json_plugins_setup(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("DF_PLUGINS_SETUP=not-json\n")

    with pytest.raises(typer.Exit):
        inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.error.call_count == 1
    assert "Invalid DF_PLUGINS_SETUP" in mock_echo.error.call_args[0][0]


@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_rejects_json_array_plugins_setup(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text('DF_PLUGINS_SETUP=["a", "b"]\n')

    with pytest.raises(typer.Exit):
        inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.error.call_count == 1
    assert "Invalid DF_PLUGINS_SETUP" in mock_echo.error.call_args[0][0]


@MOCK_GET_NEWEST_IMAGE_TAG
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_resolves_newest_image_tag_for_default_image(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_get_newest_image_tag: Mock,
    tmp_path: Path,
) -> None:
    mock_get_newest_image_tag.return_value = "v1.2.3"

    context = inspect_util(directory=tmp_path, image=DF_SERVER_IMAGE, local_image=False, force_install=False)

    assert context.newest_image_tag == "v1.2.3"
    assert mock_get_newest_image_tag.call_count == 1


@pytest.mark.parametrize(
    ("image", "local_image"),
    [
        pytest.param(DF_SERVER_IMAGE, True, id="local_image"),
        pytest.param("custom/image:tag", False, id="custom_image"),
    ],
)
@MOCK_GET_NEWEST_IMAGE_TAG
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_skips_newest_image_tag_lookup(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_get_newest_image_tag: Mock,
    image: str,
    local_image: bool,
    tmp_path: Path,
) -> None:
    context = inspect_util(directory=tmp_path, image=image, local_image=local_image, force_install=False)

    assert context.newest_image_tag is None
    assert mock_get_newest_image_tag.call_count == 0


def test_is_json_object_accepts_valid_object():
    assert _is_json_object('{"a": 1}') is True


def test_is_json_object_rejects_non_object_json():
    assert _is_json_object("[1, 2, 3]") is False


def test_is_json_object_rejects_malformed_json():
    assert _is_json_object("not-json") is False


def test_is_json_object_rejects_deeply_nested_json_without_crashing():
    deeply_nested = "[" * 100_000 + "]" * 100_000

    assert _is_json_object(deeply_nested) is False


def test_expose_ports_to_host_adds_ports_from_expose_when_missing() -> None:
    services: dict[str, Any] = {"otel-collector": {"expose": [4317, 4318]}}

    expose_ports_to_host(services)

    assert services["otel-collector"]["ports"] == ["4317:4317", "4318:4318"]


def test_expose_ports_to_host_leaves_existing_ports_unchanged_when_both_present() -> None:
    services: dict[str, Any] = {"otel-collector": {"expose": [4317], "ports": ["4318:4318"]}}

    expose_ports_to_host(services)

    assert services["otel-collector"]["ports"] == ["4318:4318"]


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_rejects_invalid_log_level(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_LOG_LEVEL=verbose-9\n")

    with pytest.raises(InstallError):
        install(**install_kwargs(tmp_path))

    assert mock_echo.error.call_count == 1
    assert mock_save_compose_file.call_count == 0


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_delegates_to_install_util(mock_install_util, mock_set_default_server_directory, tmp_path):
    kwargs = install_kwargs(tmp_path)

    install_command(**kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**kwargs)
    assert set(mock_install_util.call_args[1]) == set(inspect.signature(install).parameters)


@mock.patch("deepfellow.server.install.install_util")
def test_install_command_translates_install_error_to_exit(mock_install_util, tmp_path):
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(**install_kwargs(tmp_path))

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_sets_default_server_directory_after_success(
    mock_install_util, mock_set_default_server_directory, tmp_path
):
    """Remembering the installed directory as the CLI default is a Typer-command-only side
    effect now - core install() no longer touches state.cli_config_file itself (point 4)."""
    install_command(**install_kwargs(tmp_path))

    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call(tmp_path, force=False)


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_skips_default_directory_when_install_fails(
    mock_install_util, mock_set_default_server_directory, tmp_path
):
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit):
        install_command(**install_kwargs(tmp_path))

    assert mock_set_default_server_directory.call_count == 0


@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_util_translates_bad_parameter_to_install_error(mock_echo, mock_assert_docker, tmp_path):
    """A caller outside Click (e.g. a future in-process suite install) sees a message-carrying
    InstallError instead of an unhandled, message-less typer.BadParameter."""
    mock_echo.prompt.side_effect = typer.BadParameter("Invalid docker network name")

    with pytest.raises(InstallError, match="Invalid docker network name"):
        install(**install_kwargs(tmp_path))


def test_install_command_signature_matches_install_util():
    command_params = list(inspect.signature(install_command).parameters)
    util_params = list(inspect.signature(install).parameters)

    assert command_params == util_params


@MOCK_GET_NEWEST_IMAGE_TAG
@MOCK_SAVE_ENV_FILE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_defaults_resolve_to_real_values_when_arguments_omitted(
    mock_echo,
    mock_assert_docker,
    mock_ensure_directory,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_save_env_file,
    mock_get_newest_image_tag,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_get_newest_image_tag.return_value = "deepfellow/server:1.2.3"

    install(directory=tmp_path)

    env_values = mock_save_env_file.call_args[0][1]
    assert env_values["DF_SERVER_PORT"] == DF_SERVER_PORT
    assert env_values["DF_SERVER_IMAGE"] == "deepfellow/server:1.2.3"
    assert not any(isinstance(value, OptionInfo) for value in env_values.values())
    mongo_args = mock_configure_mongo.call_args[0]
    assert mongo_args[4] == DF_MONGO_URL
    assert mongo_args[5] == DF_MONGO_DB
    assert mongo_args[7] == DF_MONGO_PORT
    assert not any(isinstance(value, OptionInfo) for value in mongo_args)
    vectordb_args = mock_configure_vector_db.call_args[0]
    assert vectordb_args[2] == int(bool(DEFAULT_VECTOR_DATABASE["provider"]["active"]))
    assert vectordb_args[3] == DEFAULT_VECTOR_DATABASE_TYPE
    assert not any(isinstance(value, OptionInfo) for value in vectordb_args)


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_accepts_builtin_workspace_template_config_without_crashing(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    tmp_path,
):
    """Regression test for BUILTIN_TEMPLATES["workspace"]["config"]["vectordb_type"] once being a
    plain string: install() calls vectordb_type.value, so splatting that config in must not crash."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(directory=tmp_path, force_install=True, **BUILTIN_TEMPLATES["workspace"]["config"])

    assert mock_configure_vector_db.call_count == 1
    assert mock_configure_vector_db.call_args[0][3] == "milvus"


def test_install_directory_defaults_to_df_server_directory():
    """Core install() no longer resolves a directory=None default against global state (that
    read/mutated state.cli_config_file even for an in-process caller main() never populated).
    It now takes a fixed, real default - mirroring how infra's core install() already worked -
    and the state-dependent resolution lives only in the Typer option's own callback."""
    assert inspect.signature(install).parameters["directory"].default == DF_SERVER_DIRECTORY


@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ECHO
def test_resolve_keeps_previous_metrics_when_confirmed(
    mock_echo: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    tmp_path: Path,
) -> None:
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_echo.confirm.return_value = True
    context = InstallContext(
        directory=tmp_path,
        newest_image_tag=None,
        original_env_content={"df_metrics_username": "orig-user", "df_metrics_password": "orig-pass"},
        log_level="INFO",
        plugins_setup="{}",
    )
    kwargs = install_kwargs(tmp_path)
    del kwargs["directory"]
    del kwargs["force_install"]

    config = resolve(context, **kwargs)

    assert config.metrics_username == "orig-user"
    assert config.metrics_password == "orig-pass"


@mock.patch("deepfellow.server.utils.install.generate_password")
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ECHO
def test_resolve_regenerates_metrics_when_not_confirmed(
    mock_echo: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_generate_password: Mock,
    tmp_path: Path,
) -> None:
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_echo.confirm.return_value = False
    mock_generate_password.side_effect = ["new-user", "new-pass"]
    context = InstallContext(
        directory=tmp_path,
        newest_image_tag=None,
        original_env_content={"df_metrics_username": "orig-user", "df_metrics_password": "orig-pass"},
        log_level="INFO",
        plugins_setup="{}",
    )
    kwargs = install_kwargs(tmp_path)
    del kwargs["directory"]
    del kwargs["force_install"]

    config = resolve(context, **kwargs)

    assert config.metrics_username == "new-user"
    assert config.metrics_password == "new-pass"
    assert mock_generate_password.call_count == 2
    assert mock_generate_password.call_args_list == [mock.call(8), mock.call(12)]


@pytest.fixture
def install_config(tmp_path: Path) -> InstallConfig:
    return InstallConfig(
        directory=tmp_path,
        port=DF_SERVER_PORT,
        image=DF_SERVER_IMAGE,
        docker_network=DF_INFRA_DOCKER_NETWORK,
        log_level="INFO",
        plugins_setup="{}",
        metrics_username="metrics-user",
        metrics_password="metrics-pass",
        mongo_env={
            "DF_MONGO_URL": DF_MONGO_URL,
            "DF_MONGO_USER": "mongo-user",
            "DF_MONGO_PASSWORD": "mongo-pass",
            "DF_MONGO_DB": DF_MONGO_DB,
        },
        custom_mongo_db_server=False,
        infra_env={"DF_INFRA__URL": "http://infra:8080", "DF_INFRA__API_KEY": "infra-api-key"},
        vectordb_envs={"DF_VECTOR_DATABASE__PROVIDER__ACTIVE": "0"},
        is_vectordb_active=False,
        is_custom_vector_db_server=False,
        vectordb_type="",
        otel=OtelConfig(envs={}, docker_compose={}),
        neo4j=Neo4jConfig(envs={}, docker_compose={}),
        local_image=False,
        dev=False,
    )


# apply() is purely programmatic (network, .env, compose, pull) - no prompts, so none of these
# tests mock echo.prompt/echo.confirm.


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_calls_ensure_network_with_configured_docker_network(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == mock.call(install_config.docker_network)


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_writes_expected_env_values(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    assert mock_save_env.call_count == 1
    env_file, env_values = mock_save_env.call_args[0]
    assert env_file == install_config.directory / ".env"
    assert env_values["DF_SERVER_PORT"] == install_config.port
    assert env_values["DF_SERVER_URL"] == f"http://localhost:{install_config.port}"
    assert env_values["DF_SERVER_IMAGE"] == install_config.image
    assert env_values["DF_INFRA_DOCKER_SUBNET"] == install_config.docker_network
    assert env_values["DF_METRICS_USERNAME"] == install_config.metrics_username
    assert env_values["DF_METRICS_PASSWORD"] == install_config.metrics_password
    assert env_values["DF_LOG_LEVEL"] == install_config.log_level
    assert env_values["DF_PLUGINS_SETUP"] == install_config.plugins_setup
    assert env_values["DF_MONGO_USER"] == install_config.mongo_env["DF_MONGO_USER"]
    assert env_values["DF_INFRA__URL"] == install_config.infra_env["DF_INFRA__URL"]
    assert env_values["DF_VECTOR_DATABASE__PROVIDER__ACTIVE"] == "0"


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_creates_default_qdrant_service_when_vectordb_active_and_not_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.is_vectordb_active = True
    install_config.is_custom_vector_db_server = False
    install_config.vectordb_type = "qdrant"

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "qdrant" in compose_dict["services"]
    assert "qdrant_data" in compose_dict["volumes"]
    assert compose_dict["services"]["server"]["depends_on"]["qdrant"] == {"condition": "service_started"}


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_creates_default_milvus_service_when_vectordb_active_and_not_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.is_vectordb_active = True
    install_config.is_custom_vector_db_server = False
    install_config.vectordb_type = "milvus"

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "milvus" in compose_dict["services"]
    assert "etcd" in compose_dict["services"]
    assert "minio" in compose_dict["services"]
    assert compose_dict["services"]["server"]["depends_on"]["milvus"] == {"condition": "service_healthy"}


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_add_vectordb_compose_service_when_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.is_vectordb_active = True
    install_config.is_custom_vector_db_server = True
    install_config.vectordb_type = "qdrant"

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "qdrant" not in compose_dict["services"]
    assert "milvus" not in compose_dict["services"]


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_filters_vectordb_envs_from_compose_environment_when_inactive(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    environment = compose_dict["services"]["server"]["environment"]
    assert all(not env.startswith("DF_VECTOR_DATABASE__") or "ACTIVE" in env for env in environment)


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_adds_default_mongo_service_when_not_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.custom_mongo_db_server = False

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "mongo" in compose_dict["services"]
    assert "mongo" in compose_dict["volumes"]
    assert compose_dict["services"]["server"]["depends_on"]["mongo"] == {"condition": "service_healthy"}


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_add_mongo_service_when_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.custom_mongo_db_server = True

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "mongo" not in compose_dict["services"]


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_forwards_infra_env_keys_into_compose_environment(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_INFRA__URL=${DF_INFRA__URL}" in environment
    assert "DF_INFRA__API_KEY=${DF_INFRA__API_KEY}" in environment


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_adds_otel_service_when_docker_compose_present(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.otel = OtelConfig(envs={}, docker_compose={"otel-collector": {"container_name": "otel-collector"}})

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "otel-collector" in compose_dict["services"]
    assert compose_dict["services"]["server"]["depends_on"]["otel-collector"] == {"condition": "service_started"}


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_appends_otel_tracing_envs_when_enabled(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.otel = OtelConfig(
        envs={"DF_OTEL_TRACING_ENABLED": "true", "DF_OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4317"},
        docker_compose={},
    )

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}" in environment
    assert "DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}" in environment


@pytest.mark.parametrize(
    "otel_envs",
    [
        {"DF_OTEL_TRACING_ENABLED": "true"},
        {"DF_OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4317"},
        {"DF_OTEL_TRACING_ENABLED": "false", "DF_OTEL_EXPORTER_OTLP_ENDPOINT": "http://otel:4317"},
    ],
    ids=("tracing_enabled_only", "endpoint_only", "tracing_explicitly_false"),
)
@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_append_otel_tracing_envs_when_only_one_var_present(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    otel_envs: dict[str, str],
    install_config: InstallConfig,
) -> None:
    install_config.otel = OtelConfig(envs=otel_envs, docker_compose={})

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}" not in environment
    assert "DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}" not in environment


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_adds_default_neo4j_service_when_docker_compose_present(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.neo4j = Neo4jConfig(
        envs={
            "DF_GRAPHITI__ENABLED": "true",
            "DF_GRAPHITI__NEO4J_URI": DF_NEO4J_URI,
            "DF_GRAPHITI__NEO4J_USER": "neo4j",
            "DF_GRAPHITI__NEO4J_PASSWORD": "neo4j-pass",
        },
        docker_compose=DOCKER_COMPOSE_NEO4J,
    )

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "neo4j" in compose_dict["services"]
    assert "neo4j_data" in compose_dict["volumes"]
    assert compose_dict["services"]["server"]["depends_on"]["neo4j"] == {"condition": "service_healthy"}
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_GRAPHITI__ENABLED=${DF_GRAPHITI__ENABLED}" in environment
    assert "DF_GRAPHITI__NEO4J_URI=${DF_GRAPHITI__NEO4J_URI}" in environment
    assert "DF_GRAPHITI__NEO4J_USER=${DF_GRAPHITI__NEO4J_USER}" in environment
    assert "DF_GRAPHITI__NEO4J_PASSWORD=${DF_GRAPHITI__NEO4J_PASSWORD}" in environment


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_add_neo4j_service_when_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.neo4j = Neo4jConfig(
        envs={
            "DF_GRAPHITI__ENABLED": "true",
            "DF_GRAPHITI__NEO4J_URI": "bolt://custom-neo4j:7687",
            "DF_GRAPHITI__NEO4J_USER": "custom-user",
            "DF_GRAPHITI__NEO4J_PASSWORD": "custom-pass",
        },
        docker_compose={},
    )

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "neo4j" not in compose_dict["services"]
    assert "neo4j_data" not in compose_dict["volumes"]
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_GRAPHITI__ENABLED=${DF_GRAPHITI__ENABLED}" in environment


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_sets_pull_policy_never_when_local_image(
    mock_echo: Mock,
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
    assert compose_dict["services"]["server"]["pull_policy"] == "never"


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_set_pull_policy_when_not_local_image(
    mock_echo: Mock,
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
    assert "pull_policy" not in compose_dict["services"]["server"]


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_creates_plugins_directory_and_mounts_volume(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    apply(install_config)

    plugins_directory = install_config.directory / "plugins"
    assert plugins_directory.is_dir()
    compose_dict = mock_save_compose.call_args[0][0]
    volumes = compose_dict["services"]["server"]["volumes"]
    assert f"{DF_SERVER_STORAGE_DIRECTORY}:/app/storage" in volumes
    assert f"{plugins_directory.as_posix()}:/app/plugins" in volumes


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_exits_when_plugins_directory_mkdir_fails(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    plugins_directory = install_config.directory / "plugins"
    original_mkdir = Path.mkdir

    def fake_mkdir(self: Path, *args: Any, **kwargs: Any) -> None:
        if self == plugins_directory:
            raise OSError("Permission denied")
        original_mkdir(self, *args, **kwargs)

    with mock.patch.object(Path, "mkdir", autospec=True, side_effect=fake_mkdir), pytest.raises(typer.Exit):
        apply(install_config)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(f"Unable to create {plugins_directory}: Permission denied.")
    assert mock_save_compose.call_count == 0


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_dev_mode_exposes_ports_and_warns(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.is_vectordb_active = True
    install_config.is_custom_vector_db_server = False
    install_config.vectordb_type = "qdrant"
    install_config.dev = True

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert compose_dict["services"]["qdrant"]["ports"] == ["6333:6333", "6334:6334", "6335:6335"]
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_dev_mode_false_does_not_expose_ports_or_warn(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.is_vectordb_active = True
    install_config.is_custom_vector_db_server = False
    install_config.vectordb_type = "qdrant"
    install_config.dev = False

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "ports" not in compose_dict["services"]["qdrant"]
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_calls_save_compose_file_with_expected_path_and_network(
    mock_echo: Mock,
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
    assert compose_file == install_config.directory / DOCKER_COMPOSE_CONFIG_FILENAME
    assert compose_dict["networks"] == {install_config.docker_network: {"external": True}}


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_pulls_docker_image(
    mock_echo: Mock,
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


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_raises_exit_when_docker_compose_pull_fails(
    mock_echo: Mock,
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


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_prints_success_message_without_prompts(
    mock_echo: Mock,
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
