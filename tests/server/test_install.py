# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the server install command."""

import json
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import typer

from deepfellow.common.config import read_env_file
from deepfellow.common.defaults import VectorDBTypeChoice
from deepfellow.server.install import install

MOCK_ECHO = mock.patch("deepfellow.server.install.echo")
MOCK_ASSERT_DOCKER = mock.patch("deepfellow.server.install.assert_docker")
MOCK_ENSURE_DIRECTORY = mock.patch("deepfellow.server.install.ensure_directory")
MOCK_ENSURE_NETWORK = mock.patch("deepfellow.server.install.ensure_network")
MOCK_CONFIGURE_MONGO = mock.patch("deepfellow.server.install.configure_mongo")
MOCK_CONFIGURE_INFRA = mock.patch("deepfellow.server.install.configure_infra")
MOCK_CONFIGURE_VECTOR_DB = mock.patch("deepfellow.server.install.configure_vector_db")
MOCK_CONFIGURE_OTEL = mock.patch("deepfellow.server.install.configure_otel")
MOCK_RUN = mock.patch("deepfellow.server.install.run")
MOCK_SAVE_COMPOSE_FILE = mock.patch("deepfellow.server.install.save_compose_file")
MOCK_SET_DEFAULT_SERVER_DIRECTORY = mock.patch("deepfellow.server.install.set_default_server_directory")


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
