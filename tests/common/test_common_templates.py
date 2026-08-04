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
from typing import TYPE_CHECKING, cast
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.common.templates import (
    InstallTemplate,
    PostStartAction,
    coerce_config_types,
    dispatch_post_start_action,
    load_yaml_template,
    run_validations,
    validate_action_functions,
    validate_action_kwargs,
    validate_template,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_dispatch_post_start_action_calls_registered_function_with_kwargs() -> None:
    _mock_func = Mock()
    registry: dict[str, Callable[..., None]] = {"some.function": _mock_func}
    action: PostStartAction = {"function": "some.function", "kwargs": {"a": 1, "b": "two"}}

    dispatch_post_start_action(action, registry)

    assert _mock_func.call_count == 1
    assert _mock_func.call_args == mock.call(a=1, b="two")


def test_dispatch_post_start_action_raises_install_error_when_function_unknown() -> None:
    action: PostStartAction = {"function": "unknown.action", "kwargs": {}}

    with pytest.raises(InstallError, match=re.escape("Unknown post-start action function: unknown.action")):
        dispatch_post_start_action(action, {})


def test_dispatch_post_start_action_wraps_typer_exit_from_registered_function() -> None:
    _mock_func = Mock(side_effect=typer.Exit(1))
    registry: dict[str, Callable[..., None]] = {"some.function": _mock_func}
    action: PostStartAction = {"function": "some.function", "kwargs": {}}

    with pytest.raises(InstallError):
        dispatch_post_start_action(action, registry)


def test_dispatch_post_start_action_raises_install_error_when_kwargs_dont_match_signature() -> None:
    def registered_function(name: str) -> None:
        pass

    registry = {"some.function": registered_function}
    action: PostStartAction = {"function": "some.function", "kwargs": {"typo_name": "x"}}

    with pytest.raises(InstallError, match=re.escape("Post-start action 'some.function' called with invalid kwargs")):
        dispatch_post_start_action(action, registry)


def test_dispatch_post_start_action_does_not_mask_a_type_error_raised_inside_the_function_body() -> None:
    def buggy_function(count: int) -> None:
        count + None  # type: ignore[operator]

    registry = {"some.function": buggy_function}
    action: PostStartAction = {"function": "some.function", "kwargs": {"count": 3}}

    with pytest.raises(TypeError, match=re.escape("unsupported operand type")):
        dispatch_post_start_action(action, registry)


def test_validate_template_returns_the_template_when_well_formed() -> None:
    loaded = {"config": {"port": 9000}, "post_start_actions": [{"function": "a.b", "kwargs": {"x": 1}}]}

    result = validate_template(loaded, "source")

    assert result == loaded


@pytest.mark.parametrize(
    ("loaded", "message"),
    [
        (["not", "a", "mapping"], "Template 'source' must be a mapping"),
        ({"post_start_actions": []}, "Template 'source': 'config' must be a mapping"),
        ({"config": {}}, "Template 'source': 'post_start_actions' must be a list"),
        (
            {"config": {5: "foo", "bogus": "bar"}, "post_start_actions": []},
            "Template 'source': 'config' keys must all be strings, got [5]",
        ),
        (
            {"config": {}, "post_start_actions": ["not-a-mapping"]},
            "Template 'source': post_start_actions[0] must be a mapping",
        ),
        (
            {"config": {}, "post_start_actions": [{"kwargs": {}}]},
            "Template 'source': post_start_actions[0].function must be a string",
        ),
        (
            {"config": {}, "post_start_actions": [{"function": "a.b"}]},
            "Template 'source': post_start_actions[0].kwargs must be a mapping",
        ),
        (
            {"config": {}, "post_start_actions": [], "version": 2},
            "Template 'source': unknown top-level key(s) ['version']; expected 'config' and 'post_start_actions'",
        ),
        (
            {"config": {}, "post_start_actions": [{"function": "a.b", "kwargs": {}, "kwarg": "typo"}]},
            "Template 'source': post_start_actions[0]: unknown key(s) ['kwarg']; expected 'function' and 'kwargs'",
        ),
        (
            {"config": {}, "post_start_actions": [], 2: "x", "version": 1},
            "Template 'source': unknown top-level key(s) [2, 'version']; expected 'config' and 'post_start_actions'",
        ),
        (
            {
                "config": {},
                "post_start_actions": [
                    {"function": "a.b", "kwargs": {}},
                    {"function": "a.b", "kwargs": {}, 7: "y", "extra": "z"},
                ],
            },
            "Template 'source': post_start_actions[1]: unknown key(s) [7, 'extra']; expected 'function' and 'kwargs'",
        ),
        # 'config' is entirely absent here too, but the unknown-top-level-key check runs first and
        # masks the "'config' must be a mapping" error a missing config would otherwise raise.
        (
            {"post_start_actions": [], "version": 2},
            "Template 'source': unknown top-level key(s) ['version']; expected 'config' and 'post_start_actions'",
        ),
    ],
)
def test_validate_template_raises_install_error_for_malformed_input(loaded: object, message: str) -> None:
    with pytest.raises(InstallError, match=re.escape(message)):
        validate_template(loaded, "source")


def test_load_yaml_template_loads_and_validates_a_well_formed_file(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config:\n  port: 9000\npost_start_actions:\n  - function: a.b\n    kwargs:\n      x: 1\n")

    result: InstallTemplate = load_yaml_template(str(template_file))

    assert result == {"config": {"port": 9000}, "post_start_actions": [{"function": "a.b", "kwargs": {"x": 1}}]}


def test_load_yaml_template_raises_install_error_when_path_does_not_exist(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(InstallError, match=re.escape(f"Unknown template '{missing_path}'")):
        load_yaml_template(str(missing_path))


def test_load_yaml_template_raises_install_error_when_path_is_a_directory(tmp_path: Path) -> None:
    with pytest.raises(InstallError, match=re.escape(f"Unknown template '{tmp_path}'")):
        load_yaml_template(str(tmp_path))


@mock.patch.object(Path, "is_file", side_effect=OSError("Permission denied"))
def test_load_yaml_template_raises_install_error_when_path_cannot_be_accessed(
    mock_is_file: Mock, tmp_path: Path
) -> None:
    template_file = tmp_path / "custom.yaml"

    with pytest.raises(InstallError, match=re.escape(f"Template '{template_file}' could not be accessed")):
        load_yaml_template(str(template_file))


@mock.patch.object(Path, "read_text", side_effect=OSError("Permission denied"))
def test_load_yaml_template_raises_install_error_when_file_cannot_be_read(mock_read_text: Mock, tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("config: {}\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape(f"Template '{template_file}' could not be read")):
        load_yaml_template(str(template_file))


def test_load_yaml_template_raises_install_error_when_yaml_is_malformed(tmp_path: Path) -> None:
    template_file = tmp_path / "malformed.yaml"
    template_file.write_text("config: [1, 2\npost_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape(f"Template '{template_file}' is not valid YAML")):
        load_yaml_template(str(template_file))


def test_validate_action_functions_accepts_actions_whose_function_is_in_registry() -> None:
    actions: list[PostStartAction] = [{"function": "a.b", "kwargs": {}}]

    validate_action_functions(actions, {"a.b": Mock()}, "source")


def test_validate_action_functions_raises_install_error_when_function_is_unknown() -> None:
    actions: list[PostStartAction] = [{"function": "a.typo", "kwargs": {}}]

    with pytest.raises(
        InstallError, match=re.escape("unknown post-start action function(s): post_start_actions[0].function 'a.typo'")
    ):
        validate_action_functions(actions, {"a.b": Mock()}, "source")


def test_validate_action_functions_reports_every_unknown_entry_with_its_index() -> None:
    actions: list[PostStartAction] = [
        {"function": "z.typo", "kwargs": {}},
        {"function": "a.b", "kwargs": {}},
        {"function": "z.typo", "kwargs": {}},
    ]

    with pytest.raises(
        InstallError,
        match=re.escape(
            "unknown post-start action function(s): "
            "post_start_actions[0].function 'z.typo', post_start_actions[2].function 'z.typo'"
        ),
    ):
        validate_action_functions(actions, {"a.b": Mock()}, "source")


def test_validate_action_kwargs_accepts_actions_whose_kwargs_bind_to_the_registered_function() -> None:
    def registered_function(name: str) -> None:
        pass

    actions: list[PostStartAction] = [{"function": "some.function", "kwargs": {"name": "x"}}]

    validate_action_kwargs(actions, {"some.function": registered_function}, "source")


def test_validate_action_kwargs_raises_install_error_when_kwargs_dont_bind_to_the_signature() -> None:
    def registered_function(name: str) -> None:
        pass

    actions: list[PostStartAction] = [{"function": "some.function", "kwargs": {"typo_name": "x"}}]

    with pytest.raises(InstallError, match=re.escape("post-start action 'some.function' called with invalid kwargs")):
        validate_action_kwargs(actions, {"some.function": registered_function}, "source")


def test_validate_action_kwargs_skips_actions_whose_function_is_not_in_registry() -> None:
    actions: list[PostStartAction] = [{"function": "unknown.action", "kwargs": {"anything": "x"}}]

    validate_action_kwargs(actions, {}, "source")


def test_validate_action_kwargs_accepts_a_wrong_value_type_because_it_only_checks_binding() -> None:
    def registered_function(name: str) -> None:
        pass

    # `name` binds fine positionally/by-name even though its value is a dict, not a str —
    # inspect.signature(...).bind() checks arity/parameter names only, never value types. A
    # wrong-type value like this isn't caught until registered_function itself runs.
    actions: list[PostStartAction] = [{"function": "some.function", "kwargs": {"name": {"nested": "dict"}}}]

    validate_action_kwargs(actions, {"some.function": registered_function}, "source")


def test_run_validations_runs_all_steps_when_none_raise() -> None:
    steps = [Mock(), Mock(), Mock()]

    run_validations(cast("list[Callable[[], None]]", steps))

    assert all(step.call_count == 1 for step in steps)


def test_run_validations_raises_the_bare_unnumbered_message_when_only_one_step_fails() -> None:
    original = InstallError("first problem")

    def failing_step() -> None:
        raise original

    with pytest.raises(InstallError, match=r"^first problem$") as exc_info:
        run_validations([failing_step])

    assert exc_info.value.__cause__ is original


def test_run_validations_runs_every_step_and_aggregates_all_failures_numbered_in_order() -> None:
    calls = []

    def step_a() -> None:
        calls.append("a")
        raise InstallError("problem A")

    def step_b() -> None:
        calls.append("b")

    def step_c() -> None:
        calls.append("c")
        raise InstallError("problem C")

    with pytest.raises(InstallError, match=re.escape("1. problem A\n2. problem C")):
        run_validations([step_a, step_b, step_c])

    assert calls == ["a", "b", "c"]


def test_run_validations_chains_from_the_last_failing_steps_exception_when_aggregating() -> None:
    problem_a = InstallError("problem A")
    problem_c = InstallError("problem C")

    def step_a() -> None:
        raise problem_a

    def step_b() -> None:
        pass

    def step_c() -> None:
        raise problem_c

    with pytest.raises(InstallError) as exc_info:
        run_validations([step_a, step_b, step_c])

    assert exc_info.value.__cause__ is problem_c


def test_run_validations_numbers_three_or_more_failures_consecutively_skipping_passing_steps() -> None:
    calls = []

    def step_1() -> None:
        calls.append(1)
        raise InstallError("problem one")

    def step_2() -> None:
        calls.append(2)

    def step_3() -> None:
        calls.append(3)
        raise InstallError("problem three")

    def step_4() -> None:
        calls.append(4)
        raise InstallError("problem four")

    with pytest.raises(InstallError, match=re.escape("1. problem one\n2. problem three\n3. problem four")):
        run_validations([step_1, step_2, step_3, step_4])

    assert calls == [1, 2, 3, 4]


def test_coerce_config_types_leaves_already_correctly_typed_values_untouched() -> None:
    config = {"port": 9000, "name": "workspace"}

    coerce_config_types(config, {"port": int, "name": str}, "source")

    assert config == {"port": 9000, "name": "workspace"}


def test_coerce_config_types_coerces_a_quoted_scalar_to_its_expected_type() -> None:
    config = {"port": "9000"}

    coerce_config_types(config, {"port": int}, "source")

    assert config == {"port": 9000}


def test_coerce_config_types_ignores_keys_absent_from_config() -> None:
    config = {"name": "workspace"}

    coerce_config_types(config, {"port": int, "name": str}, "source")

    assert config == {"name": "workspace"}


def test_coerce_config_types_raises_install_error_when_value_cannot_be_coerced() -> None:
    config = {"port": "not-a-number"}

    with pytest.raises(InstallError, match=re.escape("config key 'port' must be a int, got 'not-a-number'")):
        coerce_config_types(config, {"port": int}, "source")


def test_coerce_config_types_leaves_later_keys_unprocessed_after_raising_on_an_earlier_one() -> None:
    config = {"port": "not-a-number", "count": "42"}

    with pytest.raises(InstallError, match=re.escape("config key 'port' must be a int")):
        coerce_config_types(config, {"port": int, "count": int}, "source")

    # "port" raised first (dict/key_types iteration order), so the loop never reaches "count" —
    # it's left as the raw, uncoerced string rather than being coerced or dropped.
    assert config == {"port": "not-a-number", "count": "42"}


def test_coerce_config_types_raises_install_error_when_value_is_none() -> None:
    config = {"name": None}

    with pytest.raises(InstallError, match=re.escape("config key 'name' must be a str, got None")):
        coerce_config_types(config, {"name": str}, "source")


@pytest.mark.parametrize("value", [["a", "b"], {"a": 1}])
def test_coerce_config_types_raises_install_error_when_value_is_a_list_or_dict(value: object) -> None:
    config = {"name": value}

    with pytest.raises(InstallError, match=re.escape(f"config key 'name' must be a str, got {value!r}")):
        coerce_config_types(config, {"name": str}, "source")


def test_coerce_config_types_raises_install_error_when_bool_given_for_a_non_bool_expected_type() -> None:
    config = {"port": True}

    with pytest.raises(InstallError, match=re.escape("config key 'port' must be a int, got True")):
        coerce_config_types(config, {"port": int}, "source")


@pytest.mark.parametrize("value", [8086.9, float("inf"), float("nan")])
def test_coerce_config_types_raises_install_error_when_float_given_for_an_int_expected_type(value: float) -> None:
    config = {"port": value}

    with pytest.raises(InstallError, match=re.escape(f"config key 'port' must be a int, got {value!r}")):
        coerce_config_types(config, {"port": int}, "source")


def test_load_yaml_template_raises_install_error_when_loaded_content_fails_validation(tmp_path: Path) -> None:
    template_file = tmp_path / "custom.yaml"
    template_file.write_text("post_start_actions: []\n")

    with pytest.raises(InstallError, match=re.escape(f"Template '{template_file}': 'config' must be a mapping")):
        load_yaml_template(str(template_file))
