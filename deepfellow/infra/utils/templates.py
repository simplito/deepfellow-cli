# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared install-template infrastructure for `infra install --template`.

Consumed by deepfellow.infra.utils.install: inspect() resolves --template via resolve_template()
below, and resolve()'s _merge_template_config() merges the resolved config into the CLI-resolved
values, passing force_provided=True to echo.prompt/prompt_until_valid for any field that came from
the template. Without it, a template value equal to that field's original_default (e.g. this
module's own "workspace" template sets port to DF_INFRA_PORT) would be indistinguishable from
"nothing was provided" and the prompt would fire anyway. See deepfellow.common.echo.get_return_value.
"""

import copy
import json
from collections.abc import Callable
from typing import Any

from deepfellow.common.defaults import DF_INFRA_DOCKER_NETWORK, DF_INFRA_NAME, DF_INFRA_PORT, DF_INFRA_URL
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
from deepfellow.infra.utils.model_install import install as model_install_util
from deepfellow.infra.utils.service_install import install as service_install_util

POST_START_ACTION_REGISTRY: dict[str, Callable[..., None]] = {
    "infra.service.install": service_install_util,
    "infra.model.install": model_install_util,
}


def dispatch_post_start_action(action: PostStartAction) -> None:
    """Dispatch a post-start action using this module's registry.

    Args:
        action: The action to run.

    Raises:
        InstallError: see deepfellow.common.templates.dispatch_post_start_action for behavior/exceptions.
    """
    _dispatch_post_start_action(action, registry=POST_START_ACTION_REGISTRY)


OLLAMA_SERVICE_SPEC: dict[str, Any] = {
    "hardware": "GPU",
    "keep_alive": "-1",
    "is_flash_attention": True,
    "context_length": 250000,
}
CHAT_MODEL = "gemma4:e4b"
EMBEDDING_MODEL = "mxbai-embed-large"
FAST_MODEL = "qwen3.5:4b"

# Keep in sync with whatever config keys wiring infra install --template to actually consume, and
# the scalar type each key's install() parameter expects — this is a hand-maintained safety net
# against YAML typos and quoting mismatches (e.g. port: "9000"), not derived from a signature.
CONFIG_KEY_TYPES: dict[str, type] = {
    "port": int,
    "infra_name": str,
    "infra_url": str,
    "docker_network": str,
}
VALID_CONFIG_KEYS = set(CONFIG_KEY_TYPES)

BUILTIN_TEMPLATES: dict[str, InstallTemplate] = {
    "workspace": {
        "config": {
            "port": DF_INFRA_PORT,
            "infra_name": DF_INFRA_NAME,
            "infra_url": DF_INFRA_URL,
            "docker_network": DF_INFRA_DOCKER_NETWORK,
        },
        # None of these actions set "server": install() injects it after start, from the port it
        # actually resolved (config.infra_port) - not from this module's DF_INFRA_PORT default. The
        # CLI process runs outside Docker, so it must reach infra via localhost, not config["infra_url"]
        # above (the Docker-network hostname other containers use).
        "post_start_actions": [
            {
                "function": "infra.service.install",
                "kwargs": {
                    "name": "ollama",
                    "spec": json.dumps(OLLAMA_SERVICE_SPEC),
                },
            },
            {
                "function": "infra.model.install",
                "kwargs": {"service_name": "ollama", "model_name": CHAT_MODEL},
            },
            {
                "function": "infra.model.install",
                "kwargs": {"service_name": "ollama", "model_name": EMBEDDING_MODEL},
            },
            {
                "function": "infra.model.install",
                "kwargs": {"service_name": "ollama", "model_name": FAST_MODEL},
            },
        ],
    }
}


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
            in POST_START_ACTION_REGISTRY; or a post_start_actions entry's kwargs don't bind to its
            function's signature. A single one of these that fails is raised as-is; two or more are
            reported together in one InstallError, numbered in the order checked.
    """
    template = copy.deepcopy(BUILTIN_TEMPLATES[value]) if value in BUILTIN_TEMPLATES else load_yaml_template(value)

    run_validations(
        [
            lambda: validate_config_keys(template["config"], VALID_CONFIG_KEYS, value),
            lambda: validate_action_functions(template["post_start_actions"], POST_START_ACTION_REGISTRY, value),
            lambda: validate_action_kwargs(template["post_start_actions"], POST_START_ACTION_REGISTRY, value),
            lambda: coerce_config_types(template["config"], CONFIG_KEY_TYPES, value),
        ]
    )
    return template
