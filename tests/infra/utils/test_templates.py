# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common.exceptions import InstallError
from deepfellow.infra.utils.templates import (
    BUILTIN_TEMPLATES,
    POST_START_ACTION_REGISTRY,
    dispatch_post_start_action,
    resolve_template,
)

if TYPE_CHECKING:
    from deepfellow.common.templates import PostStartAction

_WORKSPACE_OLLAMA_SPEC = {
    "hardware": "GPU",
    "keep_alive": "-1",
    "is_flash_attention": True,
    "context_length": 250000,
}


@mock.patch.dict("deepfellow.infra.utils.templates.POST_START_ACTION_REGISTRY", clear=True)
def test_dispatch_post_start_action_calls_registered_function_with_kwargs() -> None:
    mock_func = Mock()
    POST_START_ACTION_REGISTRY["infra.model.install"] = mock_func
    action: PostStartAction = {
        "function": "infra.model.install",
        "kwargs": {"service_name": "ollama", "model_name": "gemma4:e4b"},
    }

    dispatch_post_start_action(action)

    assert mock_func.call_count == 1
    assert mock_func.call_args == mock.call(service_name="ollama", model_name="gemma4:e4b")


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.utils.service_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.service_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_dispatch_post_start_action_installs_ollama_service_from_builtin_workspace_template(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_persist: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}
    action = BUILTIN_TEMPLATES["workspace"]["post_start_actions"][0]

    dispatch_post_start_action(action)

    assert mock_install_with_progress.call_count == 1
    call_kwargs = mock_install_with_progress.call_args[1]
    assert call_kwargs["data"] == {"spec": _WORKSPACE_OLLAMA_SPEC}
    assert mock_resolve.call_count == 1
    assert mock_resolve.call_args == mock.call(None)
    assert mock_persist.call_count == 1


@mock.patch("deepfellow.infra.utils.connection.persist_infra_connection")
@mock.patch("deepfellow.infra.utils.model_install.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_install.resolve_infra_connection", return_value=("http://infra:8086", "test-key")
)
def test_dispatch_post_start_action_installs_chat_model_from_builtin_workspace_template(
    mock_resolve: Mock,
    mock_install_with_progress: Mock,
    mock_persist: Mock,
) -> None:
    mock_install_with_progress.return_value = {"status": "OK"}
    action = BUILTIN_TEMPLATES["workspace"]["post_start_actions"][1]

    dispatch_post_start_action(action)

    assert mock_install_with_progress.call_count == 1
    assert mock_resolve.call_count == 1
    assert mock_resolve.call_args == mock.call(None)
    assert mock_persist.call_count == 1


def test_builtin_workspace_ollama_spec_is_json_serialized_for_service_install() -> None:
    action = BUILTIN_TEMPLATES["workspace"]["post_start_actions"][0]

    assert json.loads(action["kwargs"]["spec"]) == _WORKSPACE_OLLAMA_SPEC


def test_builtin_workspace_post_start_actions_leave_server_for_install_to_inject() -> None:
    # install() fills in "server" from the port it actually resolved, after infra is started - not
    # from this module, which has no way to know that port at template-definition time.
    actions = BUILTIN_TEMPLATES["workspace"]["post_start_actions"]

    assert len(actions) == 4
    assert all("server" not in action["kwargs"] for action in actions)


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


def test_resolve_template_loads_yaml_file_when_value_is_a_path(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n"
        "  port: 9000\n"
        "post_start_actions:\n"
        "  - function: infra.model.install\n"
        "    kwargs:\n"
        "      service_name: ollama\n"
        "      model_name: custom-model\n"
    )

    result = resolve_template(str(template_file))

    assert result == {
        "config": {"port": 9000},
        "post_start_actions": [
            {"function": "infra.model.install", "kwargs": {"service_name": "ollama", "model_name": "custom-model"}}
        ],
    }


def test_resolve_template_accepts_a_wrong_value_type_kwarg_because_binding_only_checks_arity(
    tmp_path: Path,
) -> None:
    # model_name is typed str on infra.model.install, but a mapping value still resolves cleanly —
    # validate_action_kwargs only checks that kwargs bind (arity/names), not their value types.
    # The mismatch isn't caught until infra.model.install itself runs, at dispatch time.
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: infra.model.install\n"
        "    kwargs:\n"
        "      service_name: ollama\n"
        "      model_name: {nested: dict}\n"
    )

    result = resolve_template(str(template_file))

    assert result["post_start_actions"][0]["kwargs"]["model_name"] == {"nested": "dict"}


def test_resolve_template_raises_install_error_when_config_has_unknown_key(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  prot: 9000\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=r"unknown config key\(s\) \['prot'\]"):
        resolve_template(str(template_file))


def test_resolve_template_unknown_top_level_key_masks_an_independent_config_key_error(tmp_path: Path) -> None:
    # validate_template() (structural) runs inside load_yaml_template(), before resolve_template()
    # even has a template["config"] to hand to run_validations()'s aggregated checks - so a
    # top-level structural mistake is reported alone, not aggregated with an unrelated config-key
    # mistake the way two run_validations steps would be. This pins that current, intentional
    # behavior rather than leaving it to accidentally drift.
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  prot: 9000\npost_start_actions: []\nversion: 2\n")

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    assert "unknown top-level key(s) ['version']" in message
    assert "unknown config key(s)" not in message


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
        "config: {}\npost_start_actions:\n  - function: infra.model.install\n    kwargs:\n      service_name: ollama\n"
    )

    with pytest.raises(
        InstallError, match=re.escape("post-start action 'infra.model.install' called with invalid kwargs")
    ):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_post_start_action_function_is_unknown(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config: {}\npost_start_actions:\n  - function: infra.model.instal\n    kwargs: {}\n")

    with pytest.raises(
        InstallError,
        match=re.escape("unknown post-start action function(s): post_start_actions[0].function 'infra.model.instal'"),
    ):
        resolve_template(str(template_file))


def test_resolve_template_raises_install_error_when_value_is_unknown_name() -> None:
    with pytest.raises(InstallError, match="Unknown template 'not-a-known-template'"):
        resolve_template("not-a-known-template")


def test_resolve_template_aggregates_multiple_unrelated_errors_into_one_install_error(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config:\n  prot: 9000\npost_start_actions:\n  - function: infra.model.instal\n    kwargs: {}\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    assert message.startswith("1. ")
    config_key_error = "unknown config key(s) ['prot']"
    action_function_error = "unknown post-start action function(s): post_start_actions[0].function 'infra.model.instal'"
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
        "  - function: infra.model.instal\n"
        "    kwargs: {}\n"
        "  - function: infra.model.install\n"
        "    kwargs:\n"
        "      service_name: ollama\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    config_key_error = "unknown config key(s) ['prot']"
    action_function_error = "unknown post-start action function(s): post_start_actions[0].function 'infra.model.instal'"
    action_kwargs_error = "post-start action 'infra.model.install' called with invalid kwargs"
    assert message.startswith(f"1. Template '{template_file}': {config_key_error}")
    assert message.index(config_key_error) < message.index(action_function_error) < message.index(action_kwargs_error)


def test_resolve_template_action_function_and_action_kwargs_errors_both_appear_in_order(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text(
        "config: {}\n"
        "post_start_actions:\n"
        "  - function: infra.model.instal\n"
        "    kwargs: {}\n"
        "  - function: infra.model.install\n"
        "    kwargs:\n"
        "      service_name: ollama\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    action_function_error = "unknown post-start action function(s): post_start_actions[0].function 'infra.model.instal'"
    action_kwargs_error = "post-start action 'infra.model.install' called with invalid kwargs"
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
        "  - function: infra.model.install\n"
        "    kwargs:\n"
        "      service_name: ollama\n"
    )

    with pytest.raises(InstallError) as exc_info:
        resolve_template(str(template_file))

    message = str(exc_info.value)
    action_kwargs_error = "post-start action 'infra.model.install' called with invalid kwargs"
    config_type_error = "config key 'port' must be a int, got 'not-a-number'"
    assert action_kwargs_error in message
    assert config_type_error in message
    # validate_action_kwargs runs before coerce_config_types, so its error is listed first.
    assert message.index(action_kwargs_error) < message.index(config_type_error)
