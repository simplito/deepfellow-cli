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
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from click.core import ParameterSource
from typer.models import OptionInfo
from typer.testing import CliRunner

from deepfellow.common.config import read_env_file, read_env_file_to_dict, save_env_file
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_FALKORDB,
    MILVUS_DATABASE_URL,
    MONGO_DB_INIT_SH,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import DockerError
from deepfellow.common.exceptions import DockerNetworkError, InstallError
from deepfellow.common.state import state
from deepfellow.server.install import app
from deepfellow.server.install import install as install_command
from deepfellow.server.utils.configure import FalkorDBConfig, OtelConfig, configure_infra, configure_vector_db
from deepfellow.server.utils.install import (
    _MERGEABLE_FIELDS,
    InstallConfig,
    InstallContext,
    _get_nested_env_value,
    _is_json_object,
    _merge_template_config,
    _resolve_port,
    apply,
    expose_ports_to_host,
    install,
    mergeable_field_names,
    resolve,
)
from deepfellow.server.utils.install import inspect as inspect_util
from deepfellow.server.utils.templates import BUILTIN_TEMPLATES, VALID_CONFIG_KEYS

runner = CliRunner()

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
MOCK_ENV_GET = mock.patch("deepfellow.server.utils.install.env_get")
MOCK_CONFIGURE_ECHO = mock.patch("deepfellow.server.utils.configure.echo")
MOCK_RESOLVE_TEMPLATE = mock.patch("deepfellow.server.utils.install.resolve_template")
MOCK_START_SERVER = mock.patch("deepfellow.server.utils.install.start_server")
MOCK_DISPATCH_POST_START_ACTION = mock.patch("deepfellow.server.utils.install.dispatch_post_start_action")
MOCK_RESOLVE_ADMIN_CREDS = mock.patch("deepfellow.server.utils.install.resolve_admin_creds")
MOCK_APPLY_ADMIN = mock.patch("deepfellow.server.utils.install.apply_admin")


def dummy_ctx() -> Mock:
    """A `typer.Context` stand-in for direct (non-Click) calls to `install_command()`.

    `get_parameter_source()` defaults to DEFAULT for every field, i.e. "nothing was explicitly
    passed" - matching a bare Python call, which has no real Click parsing behind it.
    """
    ctx = mock.MagicMock(spec=typer.Context)
    ctx.get_parameter_source.return_value = ParameterSource.DEFAULT
    return ctx


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
        "falkordb_active": False,
        "falkordb_url": DF_FALKORDB_URL,
        "falkordb_username": "",
        "falkordb_password": "",
        "force_install": True,
        "dev": False,
        "template": None,
        "admin_name": None,
        "admin_email": None,
        "admin_password": None,
    }


def configure_install_mocks(
    mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
) -> None:
    """Set return values required by the install() happy path."""
    mock_echo.prompt.return_value = "deepfellow-network"
    mock_configure_mongo.return_value = {}
    mock_configure_infra.return_value = {"DF_INFRA__URL": "http://infra:8080", "DF_INFRA__API_KEY": "api-key"}
    mock_configure_vector_db.return_value = (False, {"DF_VECTOR_DATABASE__PROVIDER__ACTIVE": "0"})
    mock_configure_otel.return_value = mock.Mock(envs={}, docker_compose=None, collector_config=None)


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


@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_explicit_infra_api_key_skips_local_infra_env_lookup(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(**{**install_kwargs(tmp_path), "infra_api_key": "explicit-key"})

    assert mock_env_get.call_count == 0
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "explicit-key"


@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_falls_back_to_local_infra_env_when_infra_api_key_not_provided(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = "infra-env-key"

    install(**{**install_kwargs(tmp_path), "infra_api_key": None})

    assert mock_env_get.call_count == 1
    assert mock_env_get.call_args == mock.call(DF_INFRA_DIRECTORY / ".env", "DF_INFRA_API_KEY", should_raise=False)
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "infra-env-key"


@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_empty_string_infra_api_key_falls_back_to_local_infra_env(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    tmp_path,
):
    """An explicit but empty --infra-api-key is treated as "not provided", not as an explicit
    override, so the local-infra .env lookup still runs."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = "infra-env-key"

    install(**{**install_kwargs(tmp_path), "infra_api_key": ""})

    assert mock_env_get.call_count == 1
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "infra-env-key"


@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_infra_api_key_stays_none_when_local_infra_env_lacks_key(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = None

    install(**{**install_kwargs(tmp_path), "infra_api_key": None})

    assert mock_env_get.call_count == 1
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] is None


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_template_infra_api_key_wins_over_local_infra_env_fallback(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    mock_resolve_template,
    tmp_path,
):
    """A local `infra install`'s own DF_INFRA_API_KEY must not outrank a template's infra_api_key -
    the fallback lookup has to happen after the template merge decides the value, not before, or a
    discovered local key gets baked into the merge's "explicit CLI flag" slot and blocks the
    template's value the same way an actual --infra-api-key flag would, silently and without the
    warning every other blocked field gets."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_template.return_value = {
        "config": {"infra_api_key": "templated-api-key"},
        "post_start_actions": [],
    }
    mock_env_get.return_value = "infra-env-key"

    install(**{**install_kwargs(tmp_path), "infra_api_key": None, "template": "workspace"})

    assert mock_env_get.call_count == 0
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "templated-api-key"
    assert infra_call[1]["force_provided_api_key"] is True
    assert mock_echo.warning.call_count == 0


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_local_infra_env_fallback_still_applies_when_template_omits_infra_api_key(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    mock_resolve_template,
    tmp_path,
):
    """The built-in "workspace" template deliberately omits infra_api_key (see
    deepfellow.server.utils.templates.BUILTIN_TEMPLATES) - the local-infra-env fallback must still
    apply in that case, since nothing else supplied a value."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_template.return_value = {"config": {"port": 9999}, "post_start_actions": []}
    mock_env_get.return_value = "infra-env-key"

    install(**{**install_kwargs(tmp_path), "infra_api_key": None, "template": "workspace"})

    assert mock_env_get.call_count == 1
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "infra-env-key"


@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_prior_env_infra_api_key_blocks_local_infra_env_fallback(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    tmp_path,
):
    """Regression test: a server previously pointed at its own DeepFellow Infra (its own .env has
    DF_INFRA__API_KEY set) must not have that key silently replaced by a local `infra install`'s
    key just because --infra-api-key wasn't re-passed and no --template was involved. The local
    fallback must not even be consulted; configure_infra()'s own `default=` is what restores the
    prior key."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_INFRA__API_KEY=prior-remote-key\n")
    mock_env_get.return_value = "infra-env-key"

    install(**{**install_kwargs(tmp_path), "infra_api_key": None})

    assert mock_env_get.call_count == 0
    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] is None


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


@mock.patch("deepfellow.server.utils.install.config_json_exists", return_value=True)
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_warns_when_storage_already_holds_another_installs_config(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_config_json_exists: Mock,
    tmp_path: Path,
) -> None:
    """No .env at this --directory yet, but the storage already holds another install's config.json
    - warn, since server has no --storage option to relocate storage per install the way infra
    does, so every install shares the one fixed path."""
    inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.warning.call_count == 1
    assert "shared globally" in mock_echo.warning.call_args[0][0]


@mock.patch("deepfellow.server.utils.install.config_json_exists", return_value=False)
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_does_not_warn_when_storage_has_no_config_json(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_config_json_exists: Mock,
    tmp_path: Path,
) -> None:
    inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.server.utils.install.config_json_exists", return_value=True)
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_does_not_warn_about_shared_storage_on_a_reinstall(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_config_json_exists: Mock,
    tmp_path: Path,
) -> None:
    """A re-install (prior .env present) owns that storage's config.json, so the shared-storage
    warning must stay silent - it's for a brand-new --directory only. Guards the if/elif split:
    a plain `if` here would make every routine re-install warn spuriously."""
    (tmp_path / ".env").touch()

    inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_echo.warning.call_count == 0


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


@mock.patch("deepfellow.server.utils.install.read_config_json_settings")
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_normalizes_plugins_setup_from_config_json_back_to_a_string(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_directory: Mock,
    mock_read_config_json_settings: Mock,
    tmp_path: Path,
) -> None:
    """Regression test for DFCLI-79, end to end through inspect(): unlike every other field,
    plugins_setup is kept in .env as one raw JSON-string blob rather than decomposed into
    DF_X__Y__Z keys, but config.json (the Server's own native settings store) has it as a real JSON
    object. merge_config_json_into_env() (see its own unit tests in test_common_config.py) converts
    it back to a string during the merge itself - this test just confirms inspect()'s own
    isinstance(str) check right after (and everything downstream expecting a string) sees the
    result it always has, instead of failing on a type mismatch despite valid content."""
    (tmp_path / ".env").write_text("DF_PLUGINS_SETUP={}\n")
    mock_read_config_json_settings.return_value = {"plugins_setup": {"df_anonymize_models": ["model-a"]}}

    context = inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert isinstance(context.plugins_setup, str)
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


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_rejects_non_interactive_template_missing_admin_fields(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, mock_resolve_template: Mock, tmp_path: Path
) -> None:
    state.non_interactive = True
    mock_resolve_template.return_value = {
        "config": {},
        "post_start_actions": [
            {"function": "server.create_admin", "kwargs": {"directory": tmp_path, "name": None, "email": "a@b.c"}}
        ],
    }

    with pytest.raises(InstallError, match="missing name"):
        inspect_util(
            directory=tmp_path,
            image="deepfellow-server:test",
            local_image=False,
            force_install=False,
            template="workspace",
        )

    assert mock_assert_docker.call_count == 0
    assert mock_ensure_directory.call_count == 0


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_rejects_bad_template_before_any_side_effects(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, mock_resolve_template: Mock, tmp_path: Path
) -> None:
    mock_resolve_template.side_effect = InstallError("Template 'bogus' not found.")

    with pytest.raises(InstallError, match=re.escape("Template 'bogus' not found.")):
        inspect_util(
            directory=tmp_path,
            image="deepfellow-server:test",
            local_image=False,
            force_install=False,
            template="bogus",
        )

    assert mock_assert_docker.call_count == 0
    assert mock_ensure_directory.call_count == 0


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_allows_non_interactive_template_with_all_admin_fields(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, mock_resolve_template: Mock, tmp_path: Path
) -> None:
    state.non_interactive = True
    mock_resolve_template.return_value = {
        "config": {},
        "post_start_actions": [
            {"function": "other.action", "kwargs": {}},
            {
                "function": "server.create_admin",
                "kwargs": {"directory": tmp_path, "name": "a", "email": "a@b.c", "password": "pw"},
            },
        ],
    }

    inspect_util(
        directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False, template="workspace"
    )

    assert mock_assert_docker.call_count == 1


@MOCK_RESOLVE_TEMPLATE
@MOCK_ENSURE_DIRECTORY
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_inspect_allows_interactive_template_missing_admin_fields(
    mock_echo: Mock, mock_assert_docker: Mock, mock_ensure_directory: Mock, mock_resolve_template: Mock, tmp_path: Path
) -> None:
    state.non_interactive = False
    mock_resolve_template.return_value = {
        "config": {},
        "post_start_actions": [
            {"function": "server.create_admin", "kwargs": {"directory": tmp_path, "name": None, "email": None}}
        ],
    }

    inspect_util(
        directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False, template="workspace"
    )

    assert mock_assert_docker.call_count == 1


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


@mock.patch("deepfellow.common.install.echo")
@MOCK_ASSERT_DOCKER
def test_inspect_prompts_once_for_existing_directory_when_overwrite_not_resolved(
    mock_assert_docker: Mock, mock_common_echo: Mock, tmp_path: Path
) -> None:
    mock_common_echo.confirm.return_value = True

    inspect_util(directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False)

    assert mock_common_echo.confirm.call_count == 1


@mock.patch("deepfellow.common.install.echo")
@MOCK_ASSERT_DOCKER
def test_inspect_does_not_prompt_when_overwrite_pre_resolved(
    mock_assert_docker: Mock, mock_common_echo: Mock, tmp_path: Path
) -> None:
    inspect_util(
        directory=tmp_path, image="deepfellow-server:test", local_image=False, force_install=False, overwrite=True
    )

    assert mock_common_echo.confirm.call_count == 0


def test_get_nested_env_value_returns_value_at_multi_segment_path():
    result = _get_nested_env_value({"df_infra": {"url": "http://infra:8086"}}, ("df_infra", "url"))

    assert result == "http://infra:8086"


def test_get_nested_env_value_returns_value_at_single_segment_path():
    result = _get_nested_env_value({"df_server_port": 9001}, ("df_server_port",))

    assert result == 9001


def test_get_nested_env_value_returns_none_for_missing_leaf():
    result = _get_nested_env_value({"df_infra": {}}, ("df_infra", "api_key"))

    assert result is None


def test_get_nested_env_value_returns_none_for_missing_intermediate():
    result = _get_nested_env_value({}, ("df_vector_database", "provider", "url"))

    assert result is None


def test_get_nested_env_value_returns_none_when_path_walks_through_a_non_dict():
    """A path segment can land on a plain value instead of a nested dict (e.g. a stale/malformed
    .env value) - this must report "not found" rather than raise AttributeError."""
    result = _get_nested_env_value({"df_infra": "not-a-dict"}, ("df_infra", "url"))

    assert result is None


def test_mergeable_fields_keys_are_unique():
    keys = [key for key, _path in _MERGEABLE_FIELDS]

    assert len(keys) == len(set(keys))


def test_mergeable_fields_cover_every_valid_template_config_key():
    mergeable_fields_keys = {key for key, _path in _MERGEABLE_FIELDS}

    assert mergeable_fields_keys == VALID_CONFIG_KEYS


def test_merge_template_config_applies_template_value_when_cli_arg_is_not_explicit():
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"port": 9001},
        original_env_content={},
        values={"port": DF_SERVER_PORT},
        explicitly_provided=set(),
    )

    assert merged == {"port": 9001}
    assert from_template == {"port"}
    assert blocked_by_prior_env == set()


def test_merge_template_config_explicit_cli_arg_wins_over_template_value():
    """Passing "port" in explicitly_provided must win even when the CLI value equals the
    template's - the old `merged[key] != own_default` heuristic couldn't tell an explicit flag
    that happens to equal its own default from one that was never passed at all; explicitly_provided
    is computed by the Typer command from ctx.get_parameter_source(), so it isn't fooled by that."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"port": 9001},
        original_env_content={},
        values={"port": DF_SERVER_PORT},
        explicitly_provided={"port"},
    )

    assert merged == {"port": DF_SERVER_PORT}
    assert from_template == set()
    assert blocked_by_prior_env == set()


def test_merge_template_config_preserves_prior_env_value_over_template_value():
    """A nested _MERGEABLE_FIELDS path (e.g. vectordb_url) found in a prior install's .env must
    block the template value, even though the CLI arg is not explicitly provided - and the prior
    value itself must land in `merged`, not just block the template, so a downstream prompt marked
    force_provided=True (because the key is in blocked_by_prior_env) returns the real prior value
    instead of silently falling back to the CLI's own hardcoded default."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"vectordb_url": "http://template-vectordb:19530"},
        original_env_content={"df_vector_database": {"provider": {"url": "http://prior-vectordb:19530"}}},
        values={"vectordb_url": DEFAULT_VECTOR_DATABASE["provider"]["url"]},
        explicitly_provided=set(),
    )

    assert merged == {"vectordb_url": "http://prior-vectordb:19530"}
    assert from_template == set()
    assert blocked_by_prior_env == {"vectordb_url"}


def test_merge_template_config_leaves_port_unrestored_when_blocked_by_prior_value():
    """Unlike every other field, `port` must not be restored here even when blocked - it's already
    been resolved to a real int by `_resolve_port()` before this function is ever called, and
    restoring the prior .env's raw (string) value here would silently reintroduce the exact int
    conversion `_resolve_port()` already did, with no error handling for a malformed value."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"port": 9001},
        original_env_content={"df_server_port": "9000"},
        values={"port": 9000},
        explicitly_provided=set(),
    )

    assert merged == {"port": 9000}
    assert from_template == set()
    assert blocked_by_prior_env == {"port"}


def test_merge_template_config_restores_prior_vectordb_type_as_raw_string():
    """vectordb_type is stored in .env as a plain string, not a VectorDBTypeChoice - restoring it
    here (like every other non-port field) intentionally leaves the raw string in `merged`;
    converting it back to the enum is `resolve()`'s job, not this generic, type-agnostic merge."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"vectordb_type": VectorDBTypeChoice.milvus},
        original_env_content={"df_vector_database": {"provider": {"type": "qdrant"}}},
        values={"vectordb_type": VectorDBTypeChoice(DEFAULT_VECTOR_DATABASE_TYPE)},
        explicitly_provided=set(),
    )

    assert merged == {"vectordb_type": "qdrant"}
    assert from_template == set()
    assert blocked_by_prior_env == {"vectordb_type"}


def test_merge_template_config_skips_field_absent_from_template_config():
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={},
        original_env_content={},
        values={"port": DF_SERVER_PORT},
        explicitly_provided=set(),
    )

    assert merged == {"port": DF_SERVER_PORT}
    assert from_template == set()
    assert blocked_by_prior_env == set()


def test_merge_template_config_resolves_each_field_independently():
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"port": 9001, "docker_network": "template-network"},
        original_env_content={},
        values={"port": 9999, "docker_network": DF_INFRA_DOCKER_NETWORK},
        explicitly_provided={"port"},
    )

    assert merged == {"port": 9999, "docker_network": "template-network"}
    assert from_template == {"docker_network"}
    assert blocked_by_prior_env == set()


def test_resolve_port_restores_prior_env_value_when_not_explicit():
    result = _resolve_port(DF_SERVER_PORT, {"df_server_port": 9000}, set())

    assert result == 9000


def test_resolve_port_raises_on_invalid_prior_port():
    with pytest.raises(InstallError):
        _resolve_port(DF_SERVER_PORT, {"df_server_port": "not-a-number"}, set())


def test_resolve_port_returns_cli_value_when_explicitly_provided():
    result = _resolve_port(9999, {"df_server_port": "not-a-number"}, {"port"})

    assert result == 9999


def test_resolve_port_returns_cli_value_when_no_prior_env():
    result = _resolve_port(DF_SERVER_PORT, {}, set())

    assert result == DF_SERVER_PORT


def test_merge_template_config_explicit_enum_flag_wins_over_template_vectordb_type():
    """An explicit --vectordb-type flag must still win over the template, even when its value
    equals the template's own vectordb_type value."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"vectordb_type": VectorDBTypeChoice.qdrant},
        original_env_content={},
        values={"vectordb_type": VectorDBTypeChoice.qdrant},
        explicitly_provided={"vectordb_type"},
    )

    assert merged == {"vectordb_type": VectorDBTypeChoice.qdrant}
    assert from_template == set()
    assert blocked_by_prior_env == set()


def test_merge_template_config_applies_template_enum_vectordb_type_when_cli_arg_not_explicit():
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"vectordb_type": VectorDBTypeChoice.milvus},
        original_env_content={},
        values={"vectordb_type": VectorDBTypeChoice(DEFAULT_VECTOR_DATABASE_TYPE)},
        explicitly_provided=set(),
    )

    assert merged == {"vectordb_type": VectorDBTypeChoice.milvus}
    assert from_template == {"vectordb_type"}
    assert blocked_by_prior_env == set()


def test_merge_template_config_explicit_infra_api_key_wins_over_template_value():
    """An explicit --infra-api-key flag must still win over the template."""
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"infra_api_key": "template-key"},
        original_env_content={},
        values={"infra_api_key": "explicit-key"},
        explicitly_provided={"infra_api_key"},
    )

    assert merged == {"infra_api_key": "explicit-key"}
    assert from_template == set()
    assert blocked_by_prior_env == set()


def test_merge_template_config_applies_template_infra_api_key_when_not_explicit():
    merged, from_template, blocked_by_prior_env = _merge_template_config(
        template_config={"infra_api_key": "template-key"},
        original_env_content={},
        values={"infra_api_key": None},
        explicitly_provided=set(),
    )

    assert merged == {"infra_api_key": "template-key"}
    assert from_template == {"infra_api_key"}
    assert blocked_by_prior_env == set()


@MOCK_CONFIGURE_ECHO
def test_mergeable_fields_paths_reach_real_env_values_for_qdrant(mock_configure_echo: Mock, tmp_path: Path) -> None:
    """Regression test: every _MERGEABLE_FIELDS path must resolve against a real .env produced by
    the actual configure_infra()/configure_vector_db() + save_env_file() - not a hand-guessed shape.
    The infra branch's identical mechanism once had a field pointing at a key that was never
    actually written (infra_name -> "df_infra_name" instead of the real "df_name")."""
    mock_configure_echo.prompt.side_effect = lambda *args, **kwargs: kwargs.get("default") or "placeholder"
    mock_configure_echo.prompt_until_valid.side_effect = lambda *args, **kwargs: kwargs.get("default") or "placeholder"
    mock_configure_echo.choice.return_value = "qdrant"

    infra_env = configure_infra("real-api-key", "http://infra:8086", None)
    _, vectordb_envs = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "qdrant",
        "http://custom-qdrant:6333",
        "custom-db",
        "",
        "",
        "custom-model",
        "custom-size",
        False,
        "qdrant",
    )
    env_file = tmp_path / ".env"
    save_env_file(
        env_file, {"DF_SERVER_PORT": 9001, "DF_INFRA_DOCKER_SUBNET": "custom-network", **infra_env, **vectordb_envs}
    )
    original_env_content = read_env_file_to_dict(env_file)

    expected = {
        "port": 9001,
        "docker_network": "custom-network",
        "infra_url": "http://infra:8086",
        "infra_api_key": "placeholder",
        "vectordb_url": "http://custom-qdrant:6333",
        "vectordb_database_name": None,  # qdrant's provider dict has no "db" field at all
        "embedding_model": "custom-model",
        "embedding_size": "custom-size",
        "vectordb_type": "qdrant",
    }
    for key, path in _MERGEABLE_FIELDS:
        assert _get_nested_env_value(original_env_content, path) == expected[key]


@MOCK_CONFIGURE_ECHO
def test_mergeable_fields_paths_reach_real_env_values_for_milvus(mock_configure_echo: Mock, tmp_path: Path) -> None:
    """Same regression test as the qdrant one above, for the milvus-only fields (vectordb_database_name
    is only ever written when the provider is milvus)."""
    mock_configure_echo.prompt.side_effect = lambda *args, **kwargs: kwargs.get("default") or "placeholder"
    mock_configure_echo.prompt_until_valid.side_effect = lambda *args, **kwargs: kwargs.get("default") or "placeholder"
    mock_configure_echo.choice.return_value = "milvus"

    infra_env = configure_infra("real-api-key", "http://infra:8086", None)
    _, vectordb_envs = configure_vector_db(
        "http://infra:8086",
        {},
        1,
        "milvus",
        "http://custom-milvus:19530",
        "custom-db",
        "",
        "",
        "custom-model",
        "custom-size",
        False,
        "milvus",
    )
    env_file = tmp_path / ".env"
    save_env_file(
        env_file, {"DF_SERVER_PORT": 9001, "DF_INFRA_DOCKER_SUBNET": "custom-network", **infra_env, **vectordb_envs}
    )
    original_env_content = read_env_file_to_dict(env_file)

    expected = {
        "port": 9001,
        "docker_network": "custom-network",
        "infra_url": "http://infra:8086",
        "infra_api_key": "placeholder",
        "vectordb_url": "http://custom-milvus:19530",
        "vectordb_database_name": "custom-db",
        "embedding_model": "custom-model",
        "embedding_size": "custom-size",
        "vectordb_type": "milvus",
    }
    for key, path in _MERGEABLE_FIELDS:
        assert _get_nested_env_value(original_env_content, path) == expected[key]


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

    install_command(ctx=dummy_ctx(), **kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**kwargs, explicitly_provided=set())
    assert set(mock_install_util.call_args[1]) == set(inspect.signature(install).parameters)


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_computes_explicitly_provided_from_parameter_source(
    mock_install_util, mock_set_default_server_directory, tmp_path
):
    """explicitly_provided must reflect ctx.get_parameter_source(), not merely be an empty set -
    COMMANDLINE and ENVIRONMENT both count as explicit, DEFAULT doesn't."""
    ctx = dummy_ctx()
    ctx.get_parameter_source.side_effect = lambda name: {
        "port": ParameterSource.COMMANDLINE,
        "infra_url": ParameterSource.ENVIRONMENT,
    }.get(name, ParameterSource.DEFAULT)

    install_command(ctx=ctx, **install_kwargs(tmp_path))

    assert mock_install_util.call_args[1]["explicitly_provided"] == {"port", "infra_url"}


@mock.patch("deepfellow.common.validation.validate_email_lib")
@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_reads_admin_credentials_from_env_vars(
    mock_install_util, mock_set_default_server_directory, mock_validate_email_lib, tmp_path
):
    """--admin-name/--admin-email/--admin-password must be settable via DF_SERVER_ADMIN_* env vars,
    so scripted/non-interactive installs don't have to pass the password as a CLI argument (which
    would leak it into shell history and process listings)."""
    mock_validate_email_lib.return_value = SimpleNamespace(email="admin@example.com")

    result = runner.invoke(
        app,
        ["--directory", str(tmp_path), "--force-install"],
        env={
            "DF_SERVER_ADMIN_NAME": "Admin User",
            "DF_SERVER_ADMIN_EMAIL": "admin@example.com",
            "DF_SERVER_ADMIN_PASSWORD": "Password1!",
        },
    )

    assert result.exit_code == 0, result.output
    assert mock_install_util.call_args[1]["admin_name"] == "Admin User"
    assert mock_install_util.call_args[1]["admin_email"] == "admin@example.com"
    assert mock_install_util.call_args[1]["admin_password"] == "Password1!"


@mock.patch("deepfellow.server.install.install_util")
def test_install_command_translates_install_error_to_exit(mock_install_util, tmp_path):
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(ctx=dummy_ctx(), **install_kwargs(tmp_path))

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_sets_default_server_directory_after_success(
    mock_install_util, mock_set_default_server_directory, tmp_path
):
    """Remembering the installed directory as the CLI default is a Typer-command-only side
    effect now - core install() no longer touches state.cli_config_file itself (point 4)."""
    install_command(ctx=dummy_ctx(), **install_kwargs(tmp_path))

    assert mock_set_default_server_directory.call_count == 1
    assert mock_set_default_server_directory.call_args == mock.call(tmp_path, force=False)


@mock.patch("deepfellow.server.install.set_default_server_directory")
@mock.patch("deepfellow.server.install.install_util")
def test_install_command_skips_default_directory_when_install_fails(
    mock_install_util, mock_set_default_server_directory, tmp_path
):
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit):
        install_command(ctx=dummy_ctx(), **install_kwargs(tmp_path))

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
def test_install_reads_prior_vectordb_type_as_default_for_reconfigure_prompt(
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
    """A prior install's vector DB type lives in original_env_content as a nested
    df_vector_database.provider.type entry (env_to_dict nests on "__"), not under a flat
    "df_vector_database__provider__type" key - resolve() must read it back via the nested path
    so a reconfigure's interactive prompt defaults to the type actually configured, instead of
    silently falling back to the CLI/template value every time."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_VECTOR_DATABASE__PROVIDER__TYPE=milvus\n")

    install(**install_kwargs(tmp_path))

    assert mock_configure_vector_db.call_args[0][11] == "milvus"


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_falls_back_to_default_vectordb_type_when_prior_env_value_is_flat(
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
    """A hand-edited flat DF_VECTOR_DATABASE value (rather than the nested __PROVIDER__TYPE shape
    env_to_dict produces) must read back as "not found" and fall back to the CLI/template default,
    not raise AttributeError from treating a plain string as a nested dict."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_VECTOR_DATABASE=not-a-dict\n")

    install(**install_kwargs(tmp_path))

    assert mock_configure_vector_db.call_args[0][11] == DEFAULT_VECTOR_DATABASE_TYPE


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
        resolved_template=None,
        directory=tmp_path,
        newest_image_tag=None,
        original_env_content={"df_metrics_username": "orig-user", "df_metrics_password": "orig-pass"},
        log_level="INFO",
        plugins_setup="{}",
    )
    kwargs = install_kwargs(tmp_path)
    del kwargs["directory"]
    del kwargs["force_install"]
    del kwargs["template"]
    del kwargs["admin_name"]
    del kwargs["admin_email"]
    del kwargs["admin_password"]

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
        resolved_template=None,
        directory=tmp_path,
        newest_image_tag=None,
        original_env_content={"df_metrics_username": "orig-user", "df_metrics_password": "orig-pass"},
        log_level="INFO",
        plugins_setup="{}",
    )
    kwargs = install_kwargs(tmp_path)
    del kwargs["directory"]
    del kwargs["force_install"]
    del kwargs["template"]
    del kwargs["admin_name"]
    del kwargs["admin_email"]
    del kwargs["admin_password"]

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
        falkordb=FalkorDBConfig(envs={}, docker_compose={}),
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
def test_apply_writes_init_mongo_script_when_not_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    """init-mongo.sh is written here, by apply() itself - not by resolve()'s configure_mongo() -
    so a self-healing repair (which reapplies a config already resolved earlier, without calling
    resolve() again) still recreates this bind-mount source, instead of silently leaving Mongo
    without its create-user script (the exact regression this test guards against)."""
    install_config.custom_mongo_db_server = False

    apply(install_config)

    init_script = install_config.directory / "init-mongo.sh"
    assert init_script.read_text() == MONGO_DB_INIT_SH
    assert (init_script.stat().st_mode & 0o777) == 0o755


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_write_init_mongo_script_when_custom(
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

    assert not (install_config.directory / "init-mongo.sh").exists()


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_exits_when_init_mongo_script_write_fails(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.custom_mongo_db_server = False
    init_script = install_config.directory / "init-mongo.sh"

    def fake_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == init_script:
            raise OSError("Permission denied")
        return len(args[0]) if args else 0

    with mock.patch.object(Path, "write_text", autospec=True, side_effect=fake_write_text), pytest.raises(typer.Exit):
        apply(install_config)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(f"Unable to write {init_script.as_posix()}: Permission denied.")
    assert mock_save_compose.call_count == 0


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


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_writes_otel_collector_config_when_present(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    """otel-collector-config.yaml is written here, by apply() itself - not by resolve()'s
    configure_otel() - so a self-healing repair (which reapplies a config already resolved
    earlier, without calling resolve() again) still recreates this bind-mount source too."""
    collector_config = {"service": {"pipelines": {}}}
    install_config.otel = OtelConfig(envs={}, docker_compose={"otel-collector": {}}, collector_config=collector_config)

    apply(install_config)

    assert mock_save_compose.call_count == 2
    otel_call = mock_save_compose.call_args_list[0]
    assert otel_call == mock.call(
        collector_config,
        install_config.directory / "otel-collector-config.yaml",
        quiet=True,
        file_info="Open Telemetry collector configuration",
    )


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_write_otel_collector_config_when_remote(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.otel = OtelConfig(
        envs={"DF_OTEL_EXPORTER_OTLP_ENDPOINT": "http://remote:4317", "DF_OTEL_TRACING_ENABLED": "true"},
        docker_compose={},
        collector_config=None,
    )

    apply(install_config)

    assert not (install_config.directory / "otel-collector-config.yaml").exists()
    assert mock_save_compose.call_count == 1


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
def test_apply_adds_default_falkordb_service_when_docker_compose_present(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.falkordb = FalkorDBConfig(
        envs={
            "DF_GRAPH__ENABLED": "true",
            "DF_GRAPH__HOST": "falkordb",
            "DF_GRAPH__PORT": "6379",
            "DF_GRAPH__USERNAME": "",
            "DF_GRAPH__PASSWORD": "falkordb-pass",
        },
        docker_compose=DOCKER_COMPOSE_FALKORDB,
    )

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "falkordb" in compose_dict["services"]
    assert "falkordb_data" in compose_dict["volumes"]
    assert compose_dict["services"]["server"]["depends_on"]["falkordb"] == {"condition": "service_healthy"}
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_GRAPH__ENABLED=${DF_GRAPH__ENABLED}" in environment
    assert "DF_GRAPH__HOST=${DF_GRAPH__HOST}" in environment
    assert "DF_GRAPH__PORT=${DF_GRAPH__PORT}" in environment
    assert "DF_GRAPH__USERNAME=${DF_GRAPH__USERNAME}" in environment
    assert "DF_GRAPH__PASSWORD=${DF_GRAPH__PASSWORD}" in environment


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_does_not_add_falkordb_service_when_custom(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    install_config.falkordb = FalkorDBConfig(
        envs={
            "DF_GRAPH__ENABLED": "true",
            "DF_GRAPH__HOST": "custom-falkordb",
            "DF_GRAPH__PORT": "6379",
            "DF_GRAPH__USERNAME": "custom-user",
            "DF_GRAPH__PASSWORD": "custom-pass",
        },
        docker_compose={},
    )

    apply(install_config)

    compose_dict = mock_save_compose.call_args[0][0]
    assert "falkordb" not in compose_dict["services"]
    assert "falkordb_data" not in compose_dict["volumes"]
    environment = compose_dict["services"]["server"]["environment"]
    assert "DF_GRAPH__ENABLED=${DF_GRAPH__ENABLED}" in environment


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
    assert mock_echo.success.call_args == mock.call(
        "DeepFellow Server Installed.\n"
        "To start the docker image - `deepfellow server start`.\n"
        "For info about installation - `deepfellow server info`."
    )
    assert mock_echo.prompt.call_count == 0
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.install.run")
@mock.patch("deepfellow.server.utils.install.save_compose_file")
@mock.patch("deepfellow.server.utils.install.add_network_to_service")
@mock.patch("deepfellow.server.utils.install.ensure_network")
@mock.patch("deepfellow.server.utils.install.save_env_file")
@mock.patch("deepfellow.server.utils.install.echo")
def test_apply_prints_auto_start_hint_when_will_auto_start(
    mock_echo: Mock,
    mock_save_env: Mock,
    mock_ensure_network: Mock,
    mock_add_network: Mock,
    mock_save_compose: Mock,
    mock_run: Mock,
    install_config: InstallConfig,
) -> None:
    """A template with post_start_actions passes will_auto_start=True so the success message
    doesn't tell the user to run `server start` when install() is about to do that itself."""
    apply(install_config, will_auto_start=True)

    assert mock_echo.success.call_args == mock.call(
        "DeepFellow Server Installed.\n"
        "Starting it now to run the template's post-start actions.\n"
        "For info about installation - `deepfellow server info`."
    )


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_resolves_template_when_given(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    assert mock_resolve_template.call_count == 1
    assert mock_resolve_template.call_args == mock.call("workspace")


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_merges_template_config_when_cli_args_are_still_default(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    template_config = {
        "port": 9999,
        "docker_network": "templated-net",
        "infra_url": "http://templated-infra:9999",
        "infra_api_key": "templated-api-key",
        "vectordb_url": "http://templated-vdb:9999",
        "vectordb_database_name": "templated-db",
        "embedding_model": "templated-model",
        "embedding_size": "9999",
        "vectordb_type": VectorDBTypeChoice.milvus,
    }
    mock_resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    network_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert network_prompt_kwargs["from_args"] == "templated-net"
    assert network_prompt_kwargs["force_provided"] is True

    infra_call = mock_configure_infra.call_args
    assert infra_call[0][0] == "templated-api-key"
    assert infra_call[0][1] == "http://templated-infra:9999"
    assert infra_call[1]["force_provided_url"] is True
    assert infra_call[1]["force_provided_api_key"] is True

    vectordb_call = mock_configure_vector_db.call_args
    assert vectordb_call[0][3] == "milvus"
    assert vectordb_call[0][4] == "http://templated-vdb:9999"
    assert vectordb_call[0][5] == "templated-db"
    assert vectordb_call[0][8] == "templated-model"
    assert vectordb_call[0][9] == "9999"
    assert vectordb_call[1]["force_provided_type"] is True
    assert vectordb_call[1]["force_provided_url"] is True
    assert vectordb_call[1]["force_provided_database_name"] is True
    assert vectordb_call[1]["force_provided_model"] is True
    assert vectordb_call[1]["force_provided_size"] is True

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_SERVER_PORT"] == "9999"

    assert mock_echo.warning.call_count == 0


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_explicit_cli_arg_wins_over_template_config(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    template_config = {"docker_network": "templated-net", "infra_url": "http://templated-infra:9999"}
    mock_resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(
        directory=tmp_path,
        template="workspace",
        force_install=True,
        docker_network="explicit-net",
        infra_url="http://explicit:1234",
        explicitly_provided={"docker_network", "infra_url"},
    )

    network_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert network_prompt_kwargs["from_args"] == "explicit-net"
    assert network_prompt_kwargs["force_provided"] is False

    infra_call = mock_configure_infra.call_args
    assert infra_call[0][1] == "http://explicit:1234"
    assert infra_call[1]["force_provided_url"] is False


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_preserves_prior_env_value_over_template_config(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    # Regression test: a template must not silently discard a value a prior install already
    # configured in .env, even when the CLI arg for that field is still at its own default.
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_INFRA_DOCKER_SUBNET=existing-net\nDF_INFRA__URL=http://existing-infra:8086\n")
    template_config = {"docker_network": "templated-net", "infra_url": "http://templated-infra:9999"}
    mock_resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    network_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert network_prompt_kwargs["from_args"] == "existing-net"
    assert network_prompt_kwargs["force_provided"] is True
    assert network_prompt_kwargs["default"] == "existing-net"

    infra_call = mock_configure_infra.call_args
    assert infra_call[0][1] == "http://existing-infra:8086"
    assert infra_call[1]["force_provided_url"] is True

    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert "Template's 'docker_network' config value is ignored because a prior install already configured it." in (
        warning_messages
    )
    assert "Template's 'infra_url' config value is ignored because a prior install already configured it." in (
        warning_messages
    )


@mock.patch("deepfellow.server.utils.install.read_config_json_settings")
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_preserves_prior_config_json_value_over_template_config(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    mock_read_config_json_settings,
    tmp_path,
):
    """Regression test for DFCLI-55: a template must not silently discard a value that only exists
    in config.json - e.g. a field that migrated away from .env after the service's first start, so
    .env alone would see it as "unset" - and the real config.json value, not a hardcoded default,
    must be what's actually used downstream."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").touch()  # config.json is only consulted once a prior .env is confirmed
    mock_read_config_json_settings.return_value = {
        "infra_docker_subnet": "config-json-net",
        "infra": {"url": "http://config-json-infra:8086"},
    }
    template_config = {"docker_network": "templated-net", "infra_url": "http://templated-infra:9999"}
    mock_resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    network_prompt_kwargs = mock_echo.prompt.call_args_list[0][1]
    assert network_prompt_kwargs["from_args"] == "config-json-net"
    assert network_prompt_kwargs["force_provided"] is True
    assert network_prompt_kwargs["default"] == "config-json-net"

    infra_call = mock_configure_infra.call_args
    assert infra_call[0][1] == "http://config-json-infra:8086"
    assert infra_call[1]["force_provided_url"] is True
    assert infra_call[0][2]["df_infra"]["url"] == "http://config-json-infra:8086"

    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert "Template's 'docker_network' config value is ignored because a prior install already configured it." in (
        warning_messages
    )
    assert "Template's 'infra_url' config value is ignored because a prior install already configured it." in (
        warning_messages
    )


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_preserves_prior_env_vectordb_type_over_template_config(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    """A prior install's vectordb_type is restored from .env as a plain string (see
    _merge_template_config()) - resolve() must convert it back to a VectorDBTypeChoice before using
    its `.value`, not just before checking `key in already_resolved`."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_VECTOR_DATABASE__PROVIDER__TYPE=qdrant\n")
    template_config = {"vectordb_type": VectorDBTypeChoice.milvus}
    mock_resolve_template.return_value = {"config": template_config, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    vectordb_call = mock_configure_vector_db.call_args
    assert vectordb_call[0][3] == "qdrant"
    assert vectordb_call[1]["force_provided_type"] is True

    warning_messages = [call.args[0] for call in mock_echo.warning.call_args_list]
    assert "Template's 'vectordb_type' config value is ignored because a prior install already configured it." in (
        warning_messages
    )


@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_restores_prior_port_when_no_template_given(
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
    (tmp_path / ".env").write_text("DF_SERVER_PORT=9500\n")

    install(**install_kwargs(tmp_path))

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_SERVER_PORT"] == "9500"


@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_restores_prior_port_when_template_omits_port(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    (tmp_path / ".env").write_text("DF_SERVER_PORT=9500\n")
    mock_resolve_template.return_value = {"config": {"docker_network": "templated-net"}, "post_start_actions": []}

    install(directory=tmp_path, template="workspace", force_install=True)

    env_vars = read_env_file(tmp_path / ".env")
    assert env_vars["DF_SERVER_PORT"] == "9500"


@MOCK_APPLY_ADMIN
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_end_to_end_with_real_builtin_workspace_template(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_start_server,
    mock_dispatch_post_start_action,
    mock_apply_admin,
    tmp_path,
):
    """Every other template test mocks resolve_template() with a synthetic config, so the real
    BUILTIN_TEMPLATES["workspace"] the CLI actually ships is never exercised through the full
    precedence chain (merge -> resolve -> apply -> post-start dispatch). This drives it unmocked,
    only stubbing the external Docker/HTTP/prompt boundaries."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )

    install(
        directory=tmp_path,
        template="workspace",
        force_install=True,
        admin_name="Admin User",
        admin_email="admin@example.com",
        admin_password="Password1!",
    )

    vectordb_call = mock_configure_vector_db.call_args
    assert vectordb_call[0][3] == "milvus"
    assert vectordb_call[0][4] == MILVUS_DATABASE_URL
    assert vectordb_call[1]["force_provided_type"] is True
    assert vectordb_call[1]["force_provided_url"] is True

    assert mock_start_server.call_count == 1
    assert mock_start_server.call_args == mock.call(tmp_path)
    # A server.create_admin action is split into resolve_admin_creds() (no prompting here: every
    # credential came from a CLI flag) and apply_admin(), so it never reaches the generic dispatch.
    assert mock_dispatch_post_start_action.call_count == 0
    assert mock_apply_admin.call_args_list == [
        mock.call(directory=tmp_path, name="Admin User", email="admin@example.com", password="Password1!")
    ]


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_dispatches_post_start_actions_overriding_directory(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    mock_resolve_admin_creds,
    mock_apply_admin,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = None
    mock_resolve_admin_creds.return_value = ("resolved", "resolved@example.com", "Resolved12345!")
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        },
        {
            "function": "server.create_admin",
            "kwargs": {"directory": Path("/some/other/dir"), "name": "a", "email": "b", "password": "c"},
        },
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}

    install(directory=tmp_path, template="workspace", force_install=True)

    assert mock_start_server.call_count == 1
    assert mock_start_server.call_args == mock.call(tmp_path)
    assert mock_dispatch_post_start_action.call_count == 0
    assert mock_apply_admin.call_count == 2
    assert actions[0]["kwargs"]["directory"] == tmp_path
    assert actions[1]["kwargs"]["directory"] == tmp_path
    assert mock_echo.warning.call_count == 1
    warning_message = mock_echo.warning.call_args_list[0].args[0]
    assert "Post-start action 2/2 ('server.create_admin') set its own 'directory'" in warning_message


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_resolves_every_admin_credential_before_creating_any_admin_account(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_env_get: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    """DFCLI-92: the post-start-actions loop asks first and applies second. Unlike infra's
    service-spec field prompts, nothing here depends on the already-started server, so every
    action's credential prompting must precede every account creation."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = None
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        },
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        },
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    calls: list[str] = []

    def record_ask(*_args: Any, **_kwargs: Any) -> tuple[str, str, str]:
        calls.append("ask")
        return ("resolved", "resolved@example.com", "Resolved12345!")

    def record_apply(*_args: Any, **_kwargs: Any) -> bool:
        calls.append("apply")
        return True

    mock_resolve_admin_creds.side_effect = record_ask
    mock_apply_admin.side_effect = record_apply

    install(directory=tmp_path, template="workspace", force_install=True)

    assert calls == ["ask", "ask", "apply", "apply"]
    assert mock_dispatch_post_start_action.call_count == 0


@MOCK_APPLY_ADMIN
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_injects_cli_admin_flags_into_create_admin_action(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    mock_apply_admin,
    tmp_path,
):
    """--admin-name/--admin-email/--admin-password must land in the dispatched action's kwargs,
    not just satisfy the --non-interactive validation check."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = None
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}

    install(
        directory=tmp_path,
        template="workspace",
        force_install=True,
        admin_name="szymon",
        admin_email="szymon@szymon.pl",
        admin_password="Admin12345!",
    )

    assert actions[0]["kwargs"]["name"] == "szymon"
    assert actions[0]["kwargs"]["email"] == "szymon@szymon.pl"
    assert actions[0]["kwargs"]["password"] == "Admin12345!"
    assert mock_apply_admin.call_args_list == [
        mock.call(directory=tmp_path, name="szymon", email="szymon@szymon.pl", password="Admin12345!")
    ]


@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_ENV_GET
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_does_not_inject_admin_flags_into_non_create_admin_actions(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_env_get,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    tmp_path,
):
    """A non-'server.create_admin' post-start action's kwargs must be untouched by admin flags."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_env_get.return_value = None
    actions = [{"function": "server.other_action", "kwargs": {"directory": tmp_path}}]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}

    install(
        directory=tmp_path,
        template="workspace",
        force_install=True,
        admin_name="szymon",
        admin_email="szymon@szymon.pl",
        admin_password="Admin12345!",
    )

    assert "name" not in actions[0]["kwargs"]
    assert "email" not in actions[0]["kwargs"]
    assert "password" not in actions[0]["kwargs"]


@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_start_server_docker_network_error_raises_install_error(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_start_server.side_effect = DockerNetworkError("network down")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert any("Failed to start server for template post start actions: network down" in msg for msg in error_messages)
    assert mock_dispatch_post_start_action.call_count == 0


@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_start_server_typer_exit_raises_install_error(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_start_server.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert any("see console output above for details." in msg for msg in error_messages)
    assert mock_dispatch_post_start_action.call_count == 0


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_post_start_action_failure_raises_install_error(
    mock_echo,
    mock_assert_docker,
    mock_ensure_network,
    mock_configure_mongo,
    mock_configure_infra,
    mock_configure_vector_db,
    mock_configure_otel,
    mock_run,
    mock_save_compose_file,
    mock_resolve_template,
    mock_start_server,
    mock_dispatch_post_start_action,
    mock_resolve_admin_creds,
    mock_apply_admin,
    tmp_path,
):
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_admin_creds.return_value = ("resolved", "resolved@example.com", "Resolved12345!")
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_apply_admin.side_effect = InstallError("bad kwargs")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 1/1 ('server.create_admin') failed: bad kwargs\n"
        "Server is already installed and running; 0 of 1 action(s) completed before this failure."
    ) in error_messages


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_post_start_action_build_phase_failure_raises_install_error(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    """A build phase failing has its own message: nothing has been applied yet, so reporting a
    count of completed actions (as the apply pass does) would be misleading."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_resolve_admin_creds.side_effect = typer.Exit(1)

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 1/1 ('server.create_admin') could not be prepared: "
        "Installation failed; see console output above for details.\n"
        "Server is already installed and running; no post-start action has run yet."
    ) in error_messages
    assert mock_apply_admin.call_count == 0


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_post_start_action_build_phase_failure_outside_translated_set_still_raises_install_error(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_resolve_admin_creds.side_effect = ValueError("unexpected failure")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 1/1 ('server.create_admin') could not be prepared due to an unexpected "
        "failure: unexpected failure\n"
        "Server is already installed and running; no post-start action has run yet."
    ) in error_messages
    assert mock_apply_admin.call_count == 0


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_post_start_action_failure_outside_translated_set_still_raises_install_error(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_admin_creds.return_value = ("resolved", "resolved@example.com", "Resolved12345!")
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        }
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_apply_admin.side_effect = ValueError("unexpected failure")

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 1/1 ('server.create_admin') failed unexpectedly: unexpected failure\n"
        "Server is already installed and running; 0 of 1 action(s) completed before this failure."
    ) in error_messages


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_stops_dispatching_post_start_actions_after_first_failure(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    mock_resolve_admin_creds.return_value = ("resolved", "resolved@example.com", "Resolved12345!")
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        },
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": "a", "email": "b", "password": "c"},
        },
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_apply_admin.side_effect = [InstallError("bad kwargs"), None]

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    # Both actions were asked about up front, but the apply pass stops at the first failure.
    assert mock_resolve_admin_creds.call_count == 2
    assert mock_apply_admin.call_count == 1
    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 1/2 ('server.create_admin') failed: bad kwargs\n"
        "Server is already installed and running; 0 of 2 action(s) completed before this failure."
    ) in error_messages


@MOCK_APPLY_ADMIN
@MOCK_RESOLVE_ADMIN_CREDS
@MOCK_DISPATCH_POST_START_ACTION
@MOCK_START_SERVER
@MOCK_RESOLVE_TEMPLATE
@MOCK_SAVE_COMPOSE_FILE
@MOCK_RUN
@MOCK_CONFIGURE_OTEL
@MOCK_CONFIGURE_VECTOR_DB
@MOCK_CONFIGURE_INFRA
@MOCK_CONFIGURE_MONGO
@MOCK_ENSURE_NETWORK
@MOCK_ASSERT_DOCKER
@MOCK_ECHO
def test_install_runs_no_apply_phase_when_a_later_actions_ask_phase_fails(
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_ensure_network: Mock,
    mock_configure_mongo: Mock,
    mock_configure_infra: Mock,
    mock_configure_vector_db: Mock,
    mock_configure_otel: Mock,
    mock_run: Mock,
    mock_save_compose_file: Mock,
    mock_resolve_template: Mock,
    mock_start_server: Mock,
    mock_dispatch_post_start_action: Mock,
    mock_resolve_admin_creds: Mock,
    mock_apply_admin: Mock,
    tmp_path: Path,
) -> None:
    """DFCLI-92's core guarantee: the ask phase for every action runs to completion before the
    apply phase for any action starts. If the first action's ask phase already fired
    successfully, a failure asking the *second* action must still prevent the *first* action's
    apply phase from running - its side effects (creating an admin account) haven't been promised
    to the user yet. A regression back to interleaved per-action ask-then-apply would let the
    first action's apply phase slip through here."""
    configure_install_mocks(
        mock_echo, mock_configure_mongo, mock_configure_infra, mock_configure_vector_db, mock_configure_otel
    )
    actions = [
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": "a", "email": "b", "password": "c"},
        },
        {
            "function": "server.create_admin",
            "kwargs": {"directory": tmp_path, "name": None, "email": None, "password": None},
        },
    ]
    mock_resolve_template.return_value = {"config": {}, "post_start_actions": actions}
    mock_resolve_admin_creds.side_effect = [("a", "b", "c"), typer.Exit(1)]

    with pytest.raises(InstallError):
        install(directory=tmp_path, template="workspace", force_install=True)

    error_messages = [call.args[0] for call in mock_echo.error.call_args_list]
    assert (
        "Post-start action 2/2 ('server.create_admin') could not be prepared: "
        "Installation failed; see console output above for details.\n"
        "Server is already installed and running; no post-start action has run yet."
    ) in error_messages
    assert mock_apply_admin.call_count == 0


def test_install_help_lists_every_builtin_template_name() -> None:
    """--template's help text is built from sorted(BUILTIN_TEMPLATES) as a plain f-string, not
    regenerated by typer at call time - a future rename/add/remove of a built-in template would
    silently desync the displayed help from the real set with nothing failing."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for name in BUILTIN_TEMPLATES:
        assert name in result.output
