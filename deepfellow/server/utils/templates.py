# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared install-template infrastructure for `server install --template`.

`server install` merges resolve_template(...)["config"] into the CLI args passed to
echo.prompt/prompt_until_valid/choice with force_provided=True for any value that came from the
template. Without it, a template value equal to that field's original_default (e.g. this module's
own "workspace" template sets infra_url to DF_INFRA_URL and port to DF_SERVER_PORT) is
indistinguishable from "nothing was provided" and the prompt fires anyway. See
deepfellow.common.echo.get_return_value.
"""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from deepfellow.common.defaults import (
    ALLOWED_VECTOR_DB_TYPES,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_PORT,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.exceptions import InstallError
from deepfellow.common.templates import (
    InstallTemplate,
    PostStartAction,
    coerce_config_types,
    load_yaml_template,
    run_validations,
    validate_action_functions,
    validate_action_kwargs,
    validate_config_keys,
)
from deepfellow.common.templates import dispatch_post_start_action as _dispatch_post_start_action
from deepfellow.server.utils.users import create_admin as create_admin_util

POST_START_ACTION_REGISTRY: dict[str, Callable[..., Any]] = {
    "server.create_admin": create_admin_util,
}


def dispatch_post_start_action(action: PostStartAction) -> None:
    """Dispatch a post-start action using this module's registry.

    Args:
        action: The action to run.

    Raises:
        InstallError: see deepfellow.common.templates.dispatch_post_start_action for behavior/exceptions.
    """
    _dispatch_post_start_action(action, registry=POST_START_ACTION_REGISTRY)


# Keep in sync with the config keys `server install --template` consumes, and the scalar type each
# key's install() parameter expects — this is a hand-maintained safety net against YAML typos and
# quoting mismatches (e.g. port: "9000"), not derived from a signature. infra_api_key is included
# even though the built-in template omits it (see comment below).
CONFIG_KEY_TYPES: dict[str, type] = {
    "port": int,
    "infra_url": str,
    "infra_api_key": str,
    "docker_network": str,
    "vectordb_url": str,
    "vectordb_database_name": str,
    "embedding_model": str,
    "embedding_size": str,
}
# vectordb_type is a valid config key too, but it's coerced to a VectorDBTypeChoice enum by
# _coerce_vectordb_type below (with its own error message), not by the generic coerce_config_types.
VALID_CONFIG_KEYS = set(CONFIG_KEY_TYPES) | {"vectordb_type"}

BUILTIN_TEMPLATES: dict[str, InstallTemplate] = {
    "workspace": {
        "config": {
            "port": DF_SERVER_PORT,
            "infra_url": DF_INFRA_URL,
            "docker_network": DF_INFRA_DOCKER_NETWORK,
            "vectordb_type": VectorDBTypeChoice.milvus,
            "vectordb_url": MILVUS_DATABASE["provider"]["url"],
            "vectordb_database_name": MILVUS_DATABASE["provider"]["db"],
            "embedding_model": "mxbai-embed-large",
            "embedding_size": "1024",
            # infra_api_key deliberately absent: generated at infra install time, not knowable by a static template.
        },
        "post_start_actions": [
            {
                "function": "server.create_admin",
                # name/email/password deliberately None: create_admin() prompts for whichever are
                # omitted. Under --non-interactive there's no prompt to fall back on, so
                # deepfellow.server.utils.install._validate_non_interactive_post_start_actions
                # rejects this template before install rather than letting it fail after the server
                # is already installed and started.
                # directory is baked to the default DF_SERVER_DIRECTORY here, but `server install`
                # overrides it at runtime with the directory actually installed to (see
                # deepfellow.server.utils.install.install), so a --directory override is honored.
                "kwargs": {"directory": DF_SERVER_DIRECTORY, "name": None, "email": None, "password": None},
            }
        ],
    }
}


def _coerce_vectordb_type(config: dict[str, Any], source: str) -> None:
    """Normalize config["vectordb_type"] to a VectorDBTypeChoice, in place.

    Called unconditionally for every template source, since a YAML-sourced template can only ever
    produce a plain string here and needs coercing to hand a ready-to-consume value to whatever
    eventually splats `config` into install_util(**config). For a built-in template, whose value
    is already a VectorDBTypeChoice, the isinstance check below makes this a no-op.

    Args:
        config: The template's config dict to coerce, in place.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If vectordb_type is present (including an explicit null) but not a valid
            VectorDBTypeChoice value. A key that's absent entirely is left untouched.
    """
    if "vectordb_type" not in config:
        return

    vectordb_type = config["vectordb_type"]
    if isinstance(vectordb_type, VectorDBTypeChoice):
        return

    try:
        config["vectordb_type"] = VectorDBTypeChoice(vectordb_type)
    except ValueError as exc:
        raise InstallError(
            f"Template '{source}': invalid vectordb_type '{vectordb_type}'; expected one of {ALLOWED_VECTOR_DB_TYPES}."
        ) from exc


def _coerce_directory(post_start_actions: list[PostStartAction], source: str) -> None:
    """Normalize the "directory" kwarg of server.create_admin actions to a Path, in place.

    A YAML-sourced template can only ever produce a plain string here, so this coercion is needed
    regardless of template source to hand a ready-to-consume value to create_admin(), which is
    typed to take a Path. The result is expanded with .expanduser() before being resolved, unlike
    deepfellow.server.utils.options.default_directory_callback, which only calls .resolve() since
    a typed --directory value already has any "~" expanded by the shell before it gets there — a
    YAML template's string has no shell to do that for it. Without the extra .expanduser() here,
    deepfellow.server.utils.install.install's override comparison would be tripped by a template
    writing e.g. "~/.deepfellow/server" where the resolved install directory is an equivalent
    absolute path.

    Args:
        post_start_actions: The template's post_start_actions to coerce, in place.
        source: The template's --template value, echoed back in error messages.

    Raises:
        InstallError: If directory is present (including an explicit null or a blank string) but
            isn't a non-empty str or Path. A directory kwarg that's absent entirely is left
            untouched.
    """
    for action in post_start_actions:
        if action["function"] != "server.create_admin":
            continue

        if "directory" not in action["kwargs"]:
            continue

        directory = action["kwargs"]["directory"]
        if isinstance(directory, Path):
            continue

        if not isinstance(directory, str):
            raise InstallError(
                f"Template '{source}': server.create_admin directory must be a string path, "
                f"got {type(directory).__name__}."
            )

        if not directory.strip():
            raise InstallError(
                f"Template '{source}': server.create_admin directory must be a non-empty string path, "
                f"got {directory!r}."
            )

        action["kwargs"]["directory"] = Path(directory).expanduser().resolve()


def resolve_template(value: str) -> InstallTemplate:
    """Resolve a --template value: a built-in name first, else a YAML file path.

    Args:
        value: The --template option value — a BUILTIN_TEMPLATES key or a filesystem path.

    Returns:
        The resolved template, a fresh copy for a built-in name.

    Raises:
        InstallError: If value is neither a known built-in name nor a readable YAML file; if the
            file can't be read (e.g. permissions, encoding) or isn't valid YAML; if the loaded
            template doesn't have the required config/post_start_actions structure; or if any of
            the checks below fail — the template's config has an unrecognized key or a value that
            can't be coerced to its expected type; a post_start_actions entry names a function not
            in POST_START_ACTION_REGISTRY or has kwargs that don't bind to its function's
            signature; config has an invalid vectordb_type; or config has an invalid create_admin
            directory. A single one of these that fails is raised as-is; two or more are reported
            together in one InstallError, numbered in the order checked.
    """
    template = copy.deepcopy(BUILTIN_TEMPLATES[value]) if value in BUILTIN_TEMPLATES else load_yaml_template(value)

    run_validations(
        [
            lambda: validate_config_keys(template["config"], VALID_CONFIG_KEYS, value),
            lambda: validate_action_functions(template["post_start_actions"], POST_START_ACTION_REGISTRY, value),
            lambda: validate_action_kwargs(template["post_start_actions"], POST_START_ACTION_REGISTRY, value),
            lambda: coerce_config_types(template["config"], CONFIG_KEY_TYPES, value),
            lambda: _coerce_vectordb_type(template["config"], value),
            lambda: _coerce_directory(template["post_start_actions"], value),
        ]
    )
    return template
