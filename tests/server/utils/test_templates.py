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
from typing import TYPE_CHECKING
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common.defaults import VectorDBTypeChoice
from deepfellow.common.exceptions import InstallError
from deepfellow.server.utils.templates import (
    BUILTIN_TEMPLATES,
    POST_START_ACTION_REGISTRY,
    dispatch_post_start_action,
    resolve_template,
)

if TYPE_CHECKING:
    from deepfellow.common.templates import PostStartAction


@mock.patch.dict("deepfellow.server.utils.templates.POST_START_ACTION_REGISTRY", clear=True)
def test_dispatch_post_start_action_calls_registered_function_with_kwargs() -> None:
    mock_func = Mock()
    POST_START_ACTION_REGISTRY["server.create_admin"] = mock_func
    action: PostStartAction = {
        "function": "server.create_admin",
        "kwargs": {"directory": "/fake/server", "name": "admin", "email": "admin@example.com", "password": "pw"},
    }

    dispatch_post_start_action(action)

    assert mock_func.call_count == 1
    assert mock_func.call_args == mock.call(
        directory="/fake/server", name="admin", email="admin@example.com", password="pw"
    )


@mock.patch("deepfellow.server.utils.users.run")
@mock.patch("deepfellow.server.utils.users.echo")
def test_dispatch_post_start_action_creates_admin_from_builtin_workspace_template(
    mock_echo: Mock,
    mock_run: Mock,
) -> None:
    mock_echo.prompt_until_valid.side_effect = ["admin", "admin@example.com", "S3cure_pass!"]
    mock_run.return_value = "Admin created"
    action = BUILTIN_TEMPLATES["workspace"]["post_start_actions"][0]

    dispatch_post_start_action(action)

    assert mock_run.call_count == 1
    command = mock_run.call_args[0][0]
    assert command[-3:] == ["admin", "admin@example.com", "S3cure_pass!"]
    assert mock_run.call_args.kwargs["cwd"] == action["kwargs"]["directory"]


def test_resolve_template_returns_builtin_template_when_value_matches_known_name() -> None:
    result = resolve_template("workspace")

    assert result == BUILTIN_TEMPLATES["workspace"]


def test_resolve_template_returns_a_copy_of_the_builtin_template_not_a_live_reference() -> None:
    result = resolve_template("workspace")

    assert result is not BUILTIN_TEMPLATES["workspace"]
    assert result["config"] is not BUILTIN_TEMPLATES["workspace"]["config"]

    result["config"]["extra_key"] = "mutated"

    assert "extra_key" not in BUILTIN_TEMPLATES["workspace"]["config"]


def test_resolve_template_post_start_action_kwargs_are_not_a_live_reference() -> None:
    result = resolve_template("workspace")

    assert (
        result["post_start_actions"][0]["kwargs"]
        is not BUILTIN_TEMPLATES["workspace"]["post_start_actions"][0]["kwargs"]
    )

    result["post_start_actions"][0]["kwargs"]["extra_key"] = "mutated"

    assert "extra_key" not in BUILTIN_TEMPLATES["workspace"]["post_start_actions"][0]["kwargs"]


def test_builtin_workspace_vectordb_type_is_a_vectordbtypechoice_enum() -> None:
    assert BUILTIN_TEMPLATES["workspace"]["config"]["vectordb_type"] is VectorDBTypeChoice.milvus


def test_resolve_template_coerces_yaml_vectordb_type_string_to_enum(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  vectordb_type: qdrant\npost_start_actions: []\n")

    result = resolve_template(str(template_file))

    assert result["config"]["vectordb_type"] is VectorDBTypeChoice.qdrant


def test_resolve_template_raises_install_error_when_vectordb_type_is_invalid(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  vectordb_type: bogus\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape("invalid vectordb_type 'bogus'")):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_vectordb_type_is_explicitly_null(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  vectordb_type: null\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape("invalid vectordb_type 'None'")):
        resolve_template(str(template_file))


def test_resolve_template_loads_yaml_file_when_value_is_a_path(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n"
        "  port: 9000\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: /srv/deepfellow\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: null\n"
    )

    result = resolve_template(str(template_file))

    assert result == {
        "config": {"port": 9000},
        "post_start_actions": [
            {
                "function": "server.create_admin",
                "kwargs": {
                    "directory": Path("/srv/deepfellow"),
                    "name": "admin",
                    "email": "admin@example.com",
                    "password": None,
                },
            }
        ],
    }


@mock.patch.dict("deepfellow.server.utils.templates.POST_START_ACTION_REGISTRY", {"other.action": Mock()})
def test_resolve_template_leaves_non_create_admin_actions_untouched(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\npost_start_actions:\n  - function: other.action\n    kwargs:\n      directory: not-a-path-here\n"
    )

    result = resolve_template(str(template_file))

    assert result["post_start_actions"][0]["kwargs"]["directory"] == "not-a-path-here"


def test_resolve_template_raises_install_error_when_create_admin_directory_is_invalid(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: [1, 2]\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: null\n"
    )

    with pytest.raises(InstallError, match="directory must be a string path, got list"):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_create_admin_directory_is_explicitly_null(
    tmp_path: Path,
) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: null\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: pw\n"
    )

    with pytest.raises(InstallError, match="directory must be a string path, got NoneType"):
        resolve_template(str(template_file))


@pytest.mark.parametrize("directory", ["", "   "])
def test_resolve_template_raises_install_error_when_create_admin_directory_is_blank(
    directory: str, tmp_path: Path
) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        f"      directory: {directory!r}\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: pw\n"
    )

    with pytest.raises(InstallError, match=re.escape("directory must be a non-empty string path")):
        resolve_template(str(template_file))


def test_resolve_template_raises_kwargs_bind_error_without_crashing_when_directory_kwarg_is_missing(
    tmp_path: Path,
) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: pw\n"
    )

    with pytest.raises(InstallError, match=re.escape("missing a required argument: 'directory'")):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_config_has_unknown_key(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  prot: 9000\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=r"unknown config key\(s\) \['prot'\]"):
        resolve_template(str(template_file))


def test_resolve_template_coerces_a_quoted_port_string_to_int(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text('config:\n  port: "9000"\npost_start_actions: []\n')

    result = resolve_template(str(template_file))

    assert result["config"]["port"] == 9000


def test_resolve_template_raises_install_error_when_port_cannot_be_coerced_to_int(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  port: not-a-number\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape("config key 'port' must be a int, got 'not-a-number'")):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_post_start_action_kwargs_dont_bind(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: /srv/deepfellow\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
    )

    with pytest.raises(
        InstallError, match=re.escape("post-start action 'server.create_admin' called with invalid kwargs")
    ):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_post_start_action_function_is_unknown(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config: {}\npost_start_actions:\n  - function: server.create-admin\n    kwargs: {}\n")

    with pytest.raises(
        InstallError,
        match=re.escape("unknown post-start action function(s): post_start_actions[0].function 'server.create-admin'"),
    ):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_value_is_unknown_name() -> None:
    with pytest.raises(InstallError, match="Unknown template 'not-a-known-template'"):
        resolve_template("not-a-known-template")


def test_resolve_template_aggregates_multiple_unrelated_errors_into_one_install_error(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n  prot: 9000\npost_start_actions:\n  - function: server.create-admin\n    kwargs: {}\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    assert message.startswith("1. ")
    config_key_error = "unknown config key(s) ['prot']"
    action_function_error = (
        "unknown post-start action function(s): post_start_actions[0].function 'server.create-admin'"
    )
    assert config_key_error in message
    assert action_function_error in message
    # validate_config_keys runs before validate_action_functions, so its error is listed first.
    assert message.index(config_key_error) < message.index(action_function_error)


def test_resolve_template_aggregates_three_simultaneous_errors_numbered_in_order(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n"
        "  prot: 9000\n"
        "post_start_actions:\n"
        "  - function: server.create-admin\n"
        "    kwargs: {}\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: /srv/deepfellow\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    config_key_error = "unknown config key(s) ['prot']"
    action_function_error = (
        "unknown post-start action function(s): post_start_actions[0].function 'server.create-admin'"
    )
    action_kwargs_error = "post-start action 'server.create_admin' called with invalid kwargs"
    assert message.startswith(f"1. Template '{template_file}': {config_key_error}")
    assert message.index(config_key_error) < message.index(action_function_error) < message.index(action_kwargs_error)


def test_resolve_template_action_function_and_action_kwargs_errors_both_appear_in_order(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: server.create-admin\n"
        "    kwargs: {}\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: /srv/deepfellow\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    action_function_error = (
        "unknown post-start action function(s): post_start_actions[0].function 'server.create-admin'"
    )
    action_kwargs_error = "post-start action 'server.create_admin' called with invalid kwargs"
    assert action_function_error in message
    assert action_kwargs_error in message
    # validate_action_functions runs before validate_action_kwargs, so its error is listed first.
    assert message.index(action_function_error) < message.index(action_kwargs_error)


def test_resolve_template_action_kwargs_and_config_type_coercion_errors_both_appear_in_order(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n"
        "  port: not-a-number\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: /srv/deepfellow\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    action_kwargs_error = "post-start action 'server.create_admin' called with invalid kwargs"
    config_type_error = "config key 'port' must be a int, got 'not-a-number'"
    assert action_kwargs_error in message
    assert config_type_error in message
    # validate_action_kwargs runs before coerce_config_types, so its error is listed first.
    assert message.index(action_kwargs_error) < message.index(config_type_error)


def test_resolve_template_config_type_coercion_and_vectordb_type_errors_both_appear_in_order(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  port: not-a-number\n  vectordb_type: bogus\npost_start_actions: []\n")

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    config_type_error = "config key 'port' must be a int, got 'not-a-number'"
    vectordb_type_error = "invalid vectordb_type 'bogus'"
    assert config_type_error in message
    assert vectordb_type_error in message
    # coerce_config_types runs before _coerce_vectordb_type, so its error is listed first.
    assert message.index(config_type_error) < message.index(vectordb_type_error)


def test_resolve_template_vectordb_type_and_create_admin_directory_errors_both_appear_in_order(
    tmp_path: Path,
) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n"
        "  vectordb_type: bogus\n"
        "post_start_actions:\n"
        "  - function: server.create_admin\n"
        "    kwargs:\n"
        "      directory: [1, 2]\n"
        "      name: admin\n"
        "      email: admin@example.com\n"
        "      password: null\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    vectordb_type_error = "invalid vectordb_type 'bogus'"
    directory_error = "server.create_admin directory must be a string path, got list"
    assert vectordb_type_error in message
    assert directory_error in message
    # _coerce_vectordb_type runs before _coerce_directory, so its error is listed first.
    assert message.index(vectordb_type_error) < message.index(directory_error)
