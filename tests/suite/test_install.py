# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the suite install command."""

from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from click.core import ParameterSource
from typer.testing import CliRunner

from deepfellow.common.defaults import (
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_MONGO_PORT,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_PORT,
)
from deepfellow.common.exceptions import InstallError
from deepfellow.infra.utils.install import mergeable_field_names as infra_mergeable_field_names
from deepfellow.server.utils.install import mergeable_field_names as server_mergeable_field_names
from deepfellow.suite.install import app
from deepfellow.suite.install import install as install_command

runner = CliRunner()


def dummy_ctx() -> Mock:
    """A `typer.Context` stand-in for direct (non-Click) calls to `install_command()`.

    `get_parameter_source()` defaults to DEFAULT for every field, i.e. "nothing was explicitly
    passed" - matching a bare Python call, which has no real Click parsing behind it.
    """
    ctx = mock.MagicMock(spec=typer.Context)
    ctx.get_parameter_source.return_value = ParameterSource.DEFAULT
    return ctx


@pytest.fixture
def default_install_kwargs() -> dict:
    return {
        "admin_name": "Admin",
        "admin_email": "admin@example.com",
        "admin_password": "Sup3r$ecret!",
        "force_install": False,
        "resume": False,
        "infra_port": DF_INFRA_PORT,
        "infra_image": DF_INFRA_IMAGE,
        "infra_local_image": False,
        "infra_directory": DF_INFRA_DIRECTORY,
        "infra_docker_config": None,
        "infra_storage": DF_INFRA_STORAGE_DIR,
        "server_port": DF_SERVER_PORT,
        "server_image": DF_SERVER_IMAGE,
        "server_local_image": False,
        "server_directory": DF_SERVER_DIRECTORY.resolve(),
        "docker_network": DF_INFRA_DOCKER_NETWORK,
        "mongodb_port": DF_MONGO_PORT,
        "mongodb_username": "",
        "mongodb_password": "",
        "falkordb_active": False,
        "falkordb_url": DF_FALKORDB_URL,
        "falkordb_username": "",
        "falkordb_password": "",
        "otel_local": False,
    }


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_delegates_to_install_util(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(ctx=dummy_ctx(), **default_install_kwargs)

    assert mock_install_util.call_count == 1
    assert mock_install_util.call_args == mock.call(**default_install_kwargs, explicitly_provided=set())


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_forwards_resume_flag(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(ctx=dummy_ctx(), **{**default_install_kwargs, "resume": True})

    assert mock_install_util.call_args.kwargs["resume"] is True


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_computes_explicitly_provided_from_parameter_source(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    """explicitly_provided must reflect ctx.get_parameter_source(), not merely be an empty set -
    COMMANDLINE and ENVIRONMENT both count as explicit, DEFAULT doesn't - and only fields that are
    actual suite install config flags (not e.g. admin_name, which has its own separate handling)
    are tracked at all."""
    ctx = dummy_ctx()
    ctx.get_parameter_source.side_effect = lambda name: {
        "infra_port": ParameterSource.COMMANDLINE,
        "docker_network": ParameterSource.ENVIRONMENT,
        "admin_name": ParameterSource.COMMANDLINE,
    }.get(name, ParameterSource.DEFAULT)

    install_command(ctx=ctx, **default_install_kwargs)

    assert mock_install_util.call_args.kwargs["explicitly_provided"] == {"infra_port", "docker_network"}


def test_explicitly_provided_fields_stay_within_infra_and_server_mergeable_fields() -> None:
    """ "port" and "docker_network" - the two infra's/server's own `_MERGEABLE_FIELDS` keys that
    install_util() maps "infra_port"/"server_port"/"docker_network" onto for template-merge
    precedence - must keep existing on the infra/server side, independent of how many other
    suite-level flags _EXPLICITLY_PROVIDED_FIELDS also tracks for the config-ignored-warning use.
    This pins the assumption so upstream drift (e.g. a rename) fails a test instead of failing
    silently at runtime."""
    assert {"port", "docker_network"} <= infra_mergeable_field_names()
    assert {"port", "docker_network"} <= server_mergeable_field_names()


@mock.patch("deepfellow.common.validation.validate_email_lib")
@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_reads_admin_credentials_from_env_vars(
    mock_install_util: Mock,
    mock_validate_email_lib: Mock,
) -> None:
    """--admin-name/--admin-email/--admin-password must be settable via DF_SERVER_ADMIN_* env vars,
    same as server install, so scripted/non-interactive suite installs don't have to pass the
    password as a CLI argument."""
    mock_validate_email_lib.return_value = SimpleNamespace(email="admin@example.com")

    result = runner.invoke(
        app,
        [],
        env={
            "DF_SERVER_ADMIN_NAME": "Admin User",
            "DF_SERVER_ADMIN_EMAIL": "admin@example.com",
            "DF_SERVER_ADMIN_PASSWORD": "Password1!",
        },
    )

    assert result.exit_code == 0, result.output
    assert mock_install_util.call_args.kwargs["admin_name"] == "Admin User"
    assert mock_install_util.call_args.kwargs["admin_email"] == "admin@example.com"
    assert mock_install_util.call_args.kwargs["admin_password"] == "Password1!"
    assert mock_install_util.call_args.kwargs["force_install"] is False
    assert mock_install_util.call_args.kwargs["resume"] is False


_ENVVAR_BOUND_OPTIONS = (
    "DF_SERVER_ADMIN_NAME",
    "DF_SERVER_ADMIN_EMAIL",
    "DF_SERVER_ADMIN_PASSWORD",
    "DF_INFRA_PORT",
    "DF_INFRA_IMAGE",
    "DF_INFRA_DIRECTORY",
    "DF_INFRA_DOCKER_CONFIG",
    "DF_INFRA_STORAGE_DIR",
    "DF_SERVER_PORT",
    "DF_SERVER_IMAGE",
    "DF_SERVER_DIRECTORY",
    "DF_INFRA_DOCKER_NETWORK",
)


@mock.patch("deepfellow.common.validation.validate_email_lib")
@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_real_cli_defaults_match_expected_values(
    mock_install_util: Mock,
    mock_validate_email_lib: Mock,
    default_install_kwargs: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The only test that runs the ~19 new options through real Click parsing rather than calling
    install_command() directly with a mocked ctx - so a wrong typer.Option() default/callback (e.g.
    a directory option that doesn't resolve to an absolute path the way server's own does) shows up
    here even though it's invisible to every other test in this file."""

    for env_var in _ENVVAR_BOUND_OPTIONS:
        monkeypatch.delenv(env_var, raising=False)
    mock_validate_email_lib.return_value = SimpleNamespace(email="admin@example.com")

    result = runner.invoke(
        app,
        [
            "--admin-name",
            "Admin",
            "--admin-email",
            "admin@example.com",
            "--admin-password",
            "Sup3r$ecret!",
        ],
    )

    assert result.exit_code == 0, result.output
    assert mock_install_util.call_args == mock.call(**default_install_kwargs, explicitly_provided=set())


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_translates_install_error_to_exit(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    mock_install_util.side_effect = InstallError("boom")

    with pytest.raises(typer.Exit) as exc_info:
        install_command(ctx=dummy_ctx(), **default_install_kwargs)

    assert exc_info.value.exit_code == 1


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_forwards_force_install_flag(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(ctx=dummy_ctx(), **{**default_install_kwargs, "force_install": True})

    assert mock_install_util.call_args.kwargs["force_install"] is True


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_forwards_infra_and_server_options(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(
        ctx=dummy_ctx(),
        **{
            **default_install_kwargs,
            "infra_port": 9000,
            "infra_image": "myrepo/infra:dev",
            "infra_local_image": True,
            "server_port": 9001,
            "server_image": "myrepo/server:dev",
            "server_local_image": True,
            "docker_network": "my-custom-net",
        },
    )

    call_kwargs = mock_install_util.call_args.kwargs
    assert call_kwargs["infra_port"] == 9000
    assert call_kwargs["infra_image"] == "myrepo/infra:dev"
    assert call_kwargs["infra_local_image"] is True
    assert call_kwargs["server_port"] == 9001
    assert call_kwargs["server_image"] == "myrepo/server:dev"
    assert call_kwargs["server_local_image"] is True
    assert call_kwargs["docker_network"] == "my-custom-net"


@mock.patch("deepfellow.suite.install.install_util")
def test_install_command_forwards_falkordb_and_mongodb_and_otel_options(
    mock_install_util: Mock,
    default_install_kwargs: dict,
) -> None:
    install_command(
        ctx=dummy_ctx(),
        **{
            **default_install_kwargs,
            "mongodb_port": 27018,
            "mongodb_username": "dfuser",
            "mongodb_password": "dfpass",
            "falkordb_active": True,
            "falkordb_url": "my-falkordb:6379",
            "falkordb_username": "graphuser",
            "falkordb_password": "graphpass",
            "otel_local": True,
        },
    )

    call_kwargs = mock_install_util.call_args.kwargs
    assert call_kwargs["mongodb_port"] == 27018
    assert call_kwargs["mongodb_username"] == "dfuser"
    assert call_kwargs["mongodb_password"] == "dfpass"
    assert call_kwargs["falkordb_active"] is True
    assert call_kwargs["falkordb_url"] == "my-falkordb:6379"
    assert call_kwargs["falkordb_username"] == "graphuser"
    assert call_kwargs["falkordb_password"] == "graphpass"
    assert call_kwargs["otel_local"] is True
