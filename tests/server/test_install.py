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

import pytest
import typer
from typer.models import OptionInfo

from deepfellow.common.config import read_env_file
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_SERVER_PORT,
    VectorDBTypeChoice,
)
from deepfellow.server.install import install as install_command
from deepfellow.server.utils.install import install

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
MOCK_SET_DEFAULT_SERVER_DIRECTORY = mock.patch("deepfellow.server.utils.install.set_default_server_directory")
MOCK_SAVE_ENV_FILE = mock.patch("deepfellow.server.utils.install.save_env_file")
MOCK_GET_NEWEST_IMAGE_TAG = mock.patch("deepfellow.server.utils.install.get_newest_image_tag")
MOCK_DEFAULT_DIRECTORY_CALLBACK = mock.patch("deepfellow.server.utils.install.default_directory_callback")


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
    with pytest.raises(typer.Exit) as exc_info:
        install(otel_local=True, otel_url="http://existing-otel:4317")

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("--otel-local and --otel-url are mutually exclusive; pass only one.")
    assert mock_assert_docker.call_count == 0
    assert mock_configure_otel.call_count == 0
    assert mock_ensure_directory.call_count == 0


@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(**install_kwargs(tmp_path))

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_LOG_LEVEL"] == "INFO"
    assert env_vars["DF_PLUGINS_SETUP"] == "{}"


@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
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


@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
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


@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_PLUGINS_SETUP=not-json\n")

    with pytest.raises(typer.Exit) as exc_info:
        install(**install_kwargs(tmp_path))

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_save_compose_file.call_count == 0


@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_LOG_LEVEL=verbose-9\n")

    with pytest.raises(typer.Exit) as exc_info:
        install(**install_kwargs(tmp_path))

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_save_compose_file.call_count == 0


@mock.patch("deepfellow.server.install.install_util")
def test_install_command_delegates_to_install_util(mock_install_util, tmp_path):
    kwargs = install_kwargs(tmp_path)

    install_command(**kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**kwargs)
    assert set(mock_install_util.call_args[1]) == set(inspect.signature(install).parameters)


def test_install_command_signature_matches_install_util():
    command_params = list(inspect.signature(install_command).parameters)
    util_params = list(inspect.signature(install).parameters)

    assert command_params == util_params


@MOCK_GET_NEWEST_IMAGE_TAG
@MOCK_SAVE_ENV_FILE
@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
    mock_set_default_server_directory,
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


@MOCK_DEFAULT_DIRECTORY_CALLBACK
@MOCK_GET_NEWEST_IMAGE_TAG
@MOCK_SAVE_ENV_FILE
@MOCK_SET_DEFAULT_SERVER_DIRECTORY
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
def test_install_resolves_default_directory_when_omitted(
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
    mock_set_default_server_directory,
    mock_save_env_file,
    mock_get_newest_image_tag,
    mock_default_directory_callback,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_get_newest_image_tag.return_value = "deepfellow/server:1.2.3"
    mock_default_directory_callback.return_value = tmp_path

    install()

    assert mock_default_directory_callback.call_count == 1
    assert mock_default_directory_callback.call_args == mock.call(None)
    assert mock_save_env_file.call_args[0][0] == tmp_path / ".env"
