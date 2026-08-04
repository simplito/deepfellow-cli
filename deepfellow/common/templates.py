# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared install-template building blocks for the planned infra/server `--template` infrastructure.

Once `infra install --template`/`server install --template` are wired up (DFCLI-11/DFCLI-12), each
command will resolve its own independent template file and keep its own
BUILTIN_TEMPLATES/POST_START_ACTION_REGISTRY — no shared cross-command schema. Until then, this
module has no callers outside `deepfellow.infra.utils.templates`/`deepfellow.server.utils.templates`
and their own tests. It holds only the domain-agnostic pieces: the TypedDict shapes, structural
validation of a loaded template, and a registry-parameterized dispatch helper.
"""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

import yaml

from deepfellow.common.exceptions import InstallError, translate_to_install_error


class PostStartAction(TypedDict):
    """A single in-process worker-function call to run after service start."""

    function: str
    kwargs: dict[str, Any]


class InstallTemplate(TypedDict):
    """Install-time config overrides plus post-start actions, shared by built-in and user YAML templates."""

    config: dict[str, Any]
    post_start_actions: list[PostStartAction]


def _validate_post_start_action(action: object, source: str, index: int) -> PostStartAction:
    """Validate the shape of one post_start_actions[index] entry loaded from a YAML template.

    Args:
        action: The raw loaded value at post_start_actions[index].
        source: The template's --template value, echoed back in error messages.
        index: The entry's position in post_start_actions, echoed back in error messages.

    Returns:
        The validated entry, narrowed to PostStartAction.

    Raises:
        InstallError: If the entry isn't a mapping, has any key other than function/kwargs, or its
            function/kwargs fields are missing or of the wrong type.
    """
    if not isinstance(action, dict):
        raise InstallError(f"Template '{source}': post_start_actions[{index}] must be a mapping.")

    unknown_keys = set(action) - {"function", "kwargs"}
    if unknown_keys:
        raise InstallError(
            f"Template '{source}': post_start_actions[{index}]: unknown key(s) "
            f"{sorted(unknown_keys, key=str)}; expected 'function' and 'kwargs'."
        )

    function = action.get("function")
    if not isinstance(function, str):
        raise InstallError(f"Template '{source}': post_start_actions[{index}].function must be a string.")

    kwargs = action.get("kwargs")
    if not isinstance(kwargs, dict):
        raise InstallError(f"Template '{source}': post_start_actions[{index}].kwargs must be a mapping.")

    return {"function": function, "kwargs": kwargs}


def validate_template(loaded: object, source: str) -> InstallTemplate:
    """Validate the structural shape of a template loaded from YAML.

    Args:
        loaded: The raw value produced by yaml.safe_load.
        source: The template's --template value, echoed back in error messages.

    Returns:
        The validated template, narrowed to InstallTemplate.

    Raises:
        InstallError: If `loaded` isn't a mapping with a mapping `config` (with all-string keys)
            and a list `post_start_actions` of well-formed entries, or has any key other than
            `config`/`post_start_actions`.
    """
    if not isinstance(loaded, dict):
        raise InstallError(f"Template '{source}' must be a mapping with 'config' and 'post_start_actions'.")

    unknown_top_level_keys = set(loaded) - {"config", "post_start_actions"}
    if unknown_top_level_keys:
        raise InstallError(
            f"Template '{source}': unknown top-level key(s) {sorted(unknown_top_level_keys, key=str)}; "
            f"expected 'config' and 'post_start_actions'."
        )

    config = loaded.get("config")
    if not isinstance(config, dict):
        raise InstallError(f"Template '{source}': 'config' must be a mapping.")

    non_string_keys = [key for key in config if not isinstance(key, str)]
    if non_string_keys:
        raise InstallError(f"Template '{source}': 'config' keys must all be strings, got {non_string_keys!r}.")

    actions = loaded.get("post_start_actions")
    if not isinstance(actions, list):
        raise InstallError(f"Template '{source}': 'post_start_actions' must be a list.")

    validated_actions = [_validate_post_start_action(action, source, index) for index, action in enumerate(actions)]
    return {"config": config, "post_start_actions": validated_actions}


def validate_config_keys(config: dict[str, Any], valid_keys: set[str], source: str) -> None:
    """Fail fast on config keys the caller doesn't recognize, e.g. a typo in a user YAML template.

    Args:
        config: The template's config dict to check.
        valid_keys: The config keys the target install command currently accepts. Hand-maintained
            by each caller (infra/server templates modules) — not derived from the install
            command's actual signature, so it can drift if that signature changes.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If config has any key not in valid_keys.
    """
    unknown_keys = set(config) - valid_keys
    if unknown_keys:
        raise InstallError(
            f"Template '{source}': unknown config key(s) {sorted(unknown_keys)}; expected one of {sorted(valid_keys)}."
        )


def coerce_config_types(config: dict[str, Any], key_types: dict[str, type], source: str) -> None:
    """Coerce config values loaded from YAML to the scalar types the install command expects, in place.

    A YAML-sourced template can produce any scalar type for a given key depending on quoting (e.g.
    `port: "9000"` loads as str, `port: 9000` loads as int), so this normalizes each key to the
    type its install command parameter actually expects, regardless of how the template wrote it.
    Values that would only "coerce" by silently discarding information or making something up —
    None, a list/dict, a bool for a non-bool expected type (bool is a subclass of int, so
    `port: yes` would otherwise pass as `True`), or a float for an int expected type (so
    `port: 8086.9` can't silently truncate to 8086) — are rejected instead.

    Args:
        config: The template's config dict to coerce, in place. Only keys present in both config
            and key_types are touched.
        key_types: Maps every config key the target install command accepts to the type it expects
            for that key. Hand-maintained by each caller (infra/server templates modules) — not
            derived from the install command's actual signature, so it can drift if that signature
            changes.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If a present key's value is None, a list/dict, a bool for a non-bool expected
            type, a float for an int expected type, or otherwise can't be coerced to its expected type.
    """
    for key, expected_type in key_types.items():
        if key not in config:
            continue
        value = config[key]
        if type(value) is expected_type:
            continue

        if (
            value is None
            or isinstance(value, (list, dict))
            or (isinstance(value, bool) and expected_type is not bool)
            or (isinstance(value, float) and expected_type is int)
        ):
            raise InstallError(
                f"Template '{source}': config key '{key}' must be a {expected_type.__name__}, got {value!r}."
            )

        try:
            config[key] = expected_type(value)
        except (TypeError, ValueError) as exc:
            raise InstallError(
                f"Template '{source}': config key '{key}' must be a {expected_type.__name__}, got {value!r}."
            ) from exc


def validate_action_functions(
    actions: list[PostStartAction], registry: dict[str, Callable[..., None]], source: str
) -> None:
    """Fail fast on post_start_actions function names the registry doesn't recognize.

    Reports every offending entry's index alongside its function name, e.g. a template with the
    same typo'd function name in two different actions gets both locations named, not one
    deduplicated mention with no indication of which entries to fix.

    Args:
        actions: The template's validated post_start_actions to check.
        registry: Maps recognized action function names to their worker callables, e.g. each
            caller's own POST_START_ACTION_REGISTRY.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If any action's function name is not a key in registry.
    """
    unknown_entries = [
        f"post_start_actions[{index}].function '{action['function']}'"
        for index, action in enumerate(actions)
        if action["function"] not in registry
    ]
    if unknown_entries:
        raise InstallError(
            f"Template '{source}': unknown post-start action function(s): {', '.join(unknown_entries)}; "
            f"expected one of {sorted(registry)}."
        )


def validate_action_kwargs(
    actions: list[PostStartAction], registry: dict[str, Callable[..., None]], source: str
) -> None:
    """Fail fast on post_start_actions kwargs that don't bind to their worker function's signature.

    Checks arity and parameter names only, the same way dispatch_post_start_action does before
    calling the worker — this just runs the same check eagerly, at resolve_template time, instead
    of after the rest of the template's install/start side effects have already happened. It does
    not check kwargs value *types*, only that they bind: a wrong-type value (e.g. a mapping where
    the worker expects a str) still isn't caught until the worker function itself runs.

    Args:
        actions: The template's validated post_start_actions to check.
        registry: Maps recognized action function names to their worker callables, e.g. each
            caller's own POST_START_ACTION_REGISTRY. An action whose function name isn't in
            registry is skipped here — call validate_action_functions first to catch that.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If any action's kwargs don't bind to its worker function's signature.
    """
    for action in actions:
        func = registry.get(action["function"])
        if func is None:
            continue
        try:
            inspect.signature(func).bind(**action["kwargs"])
        except TypeError as exc:
            raise InstallError(
                f"Template '{source}': post-start action '{action['function']}' called with invalid kwargs: {exc}"
            ) from exc


def run_validations(steps: list[Callable[[], None]]) -> None:
    """Run each validation/coercion step, collecting failures instead of stopping at the first.

    Lets a template with several unrelated mistakes (e.g. an unknown config key and an unknown
    post-start action function) surface every mistake in one InstallError, instead of costing the
    user a fix-and-rerun round-trip per mistake. Not every step reports every one of its own
    problems internally, though — e.g. coerce_config_types still raises on only the first
    uncoercible config value it hits, leaving any later ones unreported until the next run. This
    only aggregates across steps, not within one.

    Args:
        steps: Zero-argument callables to run in order, e.g. `lambda: validate_config_keys(...)`
            for each of resolve_template's validation/coercion calls. Each may raise InstallError.

    Raises:
        InstallError: If any step raised. A single failure is raised as-is, unnumbered; two or
            more are numbered and joined into one message, in the order the steps were given.
            Either way, the raised InstallError chains from the last step's exception via `from`,
            so --debug still surfaces the original cause.
    """
    errors = []
    last_exc: InstallError | None = None
    for step in steps:
        try:
            step()
        except InstallError as exc:
            errors.append(str(exc))
            last_exc = exc
    if len(errors) == 1:
        raise InstallError(errors[0]) from last_exc
    if errors:
        raise InstallError(
            "\n".join(f"{index}. {message}" for index, message in enumerate(errors, start=1))
        ) from last_exc


def load_yaml_template(value: str) -> InstallTemplate:
    """Load and validate a template from a YAML file path.

    Args:
        value: Filesystem path to the template file (the original --template value, echoed back
            in error messages).

    Returns:
        The loaded template, validated and narrowed to InstallTemplate.

    Raises:
        InstallError: If `value` isn't a readable file; if the file can't be accessed or read
            (e.g. permissions, encoding); if it isn't valid YAML; or if the loaded template
            doesn't have the required config/post_start_actions structure.
    """
    path = Path(value)
    try:
        is_file = path.is_file()
    except OSError as exc:
        raise InstallError(f"Template '{value}' could not be accessed: {exc}") from exc
    if not is_file:
        raise InstallError(f"Unknown template '{value}': not a built-in name and not a file.")

    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallError(f"Template '{value}' could not be read: {exc}") from exc

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InstallError(f"Template '{value}' is not valid YAML: {exc}") from exc

    return validate_template(loaded, value)


@translate_to_install_error
def dispatch_post_start_action(action: PostStartAction, registry: dict[str, Callable[..., None]]) -> None:
    """Look up and call the worker function named by a post-start action, using the given registry.

    Args:
        action: The action to run.
        registry: Maps `action["function"]` names to the worker callables that implement them.

    Raises:
        InstallError: If `action["function"]` is not registered; if `action["kwargs"]` doesn't
            bind to its signature (TypeError); or if it raises typer.BadParameter, typer.Exit,
            DockerSocketNotFoundError, DockerNetworkError, or OSError (translated by
            translate_to_install_error). Other exceptions raised by the invoked function
            propagate unmodified.
    """
    func = registry.get(action["function"])
    if func is None:
        raise InstallError(f"Unknown post-start action function: {action['function']}")
    try:
        inspect.signature(func).bind(**action["kwargs"])
    except TypeError as exc:
        raise InstallError(f"Post-start action '{action['function']}' called with invalid kwargs: {exc}") from exc
    func(**action["kwargs"])
