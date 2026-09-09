# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install infra core logic."""

import random
import string
from collections.abc import Callable, Collection
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, cast

import typer

from deepfellow.common.config import (
    EnvDict,
    configure_uuid_key,
    merge_config_json_into_env,
    read_config_json_settings,
    read_env_file_to_dict,
    save_env_file,
)
from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_IMAGE,
    DF_INFRA_IMAGE_HUB,
    DF_INFRA_NAME,
    DF_INFRA_PORT,
    DF_INFRA_STORAGE_DIR,
    DF_INFRA_URL,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_INFRA,
)
from deepfellow.common.docker import (
    DockerError,
    add_network_to_service,
    ensure_network,
    get_socket,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.exceptions import DockerNetworkError, InstallError, translate_to_install_error
from deepfellow.common.generate import generate_password
from deepfellow.common.install import assert_docker, ensure_directory
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.state import state
from deepfellow.common.system import run
from deepfellow.common.templates import InstallTemplate, PostStartAction
from deepfellow.common.validation import validate_df_name, validate_url
from deepfellow.infra.utils.docker import start_infra
from deepfellow.infra.utils.model_install import apply_install as apply_model_install
from deepfellow.infra.utils.model_install import resolve_connection as resolve_model_connection
from deepfellow.infra.utils.service_install import apply_spec as apply_service_spec
from deepfellow.infra.utils.service_install import build_spec as build_service_spec
from deepfellow.infra.utils.templates import dispatch_post_start_action, resolve_template


@dataclass
class InstallContext:
    """Read-only values gathered from the environment before any prompting."""

    resolved_template: InstallTemplate | None
    directory: Path
    docker_socket: str
    newest_image_tag: str | None
    original_env_content: EnvDict  # {} if no prior .env, merged with config.json's settings if any


def inspect(
    directory: Path,
    allow_rootful: bool,
    force_install: bool,
    image: str,
    local_image: bool,
    template: str | None = None,
    overwrite: bool | None = None,
) -> InstallContext:
    """Resolve --template, then do a Docker check, directory creation, and existing .env read-back.

    Resolves and validates `template` (via resolve_template()), if given, before touching Docker or
    the filesystem, so a bad template fails fast without side effects. No network/compose writes.
    Prompts only if the target directory already exists, `force_install` is not set, and `overwrite`
    was not already resolved by the caller - see `overwrite`.

    Args:
        directory: Directory to install into.
        allow_rootful: Whether a rootful Docker socket is acceptable.
        force_install: Skips the overwrite check/prompt entirely when set.
        image: DeepFellow Infra docker image, before newest-tag resolution.
        local_image: Whether a locally built docker image is used.
        template: Optional built-in template name or path to a template YAML file.
        overwrite: Pre-answered directory-overwrite decision, passed straight through to
            `ensure_directory()`. Leave `None` to preserve today's inline prompt.

    Returns:
        InstallContext: Read-only values needed by :func:`resolve`.

    Raises:
        InstallError: If `template` is not a known built-in name or a valid, readable YAML file
            matching the expected schema. See resolve_template().
    """
    resolved_template = None
    if template is not None:
        resolved_template = resolve_template(template)

    assert_docker()
    docker_socket = get_socket(allow_rootful=allow_rootful)

    # Check if overriding existing installation
    ensure_directory(
        directory,
        error_message="Unable to create DeepFellow Infra directory.",
        force_install=force_install,
        overwrite=overwrite,
    )
    newest_image_tag = get_newest_image_tag(DF_INFRA_IMAGE_HUB) if not local_image and image == DF_INFRA_IMAGE else None

    # Prepare the starting point for .env, enriched with config.json's values (which take
    # precedence for fields that migrated there - see _config_json_exists() in
    # deepfellow/infra/env_command/set.py for the same storage dir logic)
    env_file = directory / ".env"
    original_env_content: EnvDict = read_env_file_to_dict(env_file)
    if env_file.is_file():
        # Only resolve a storage dir and read its config.json once a prior .env is confirmed for
        # this directory - otherwise a fresh install (no .env yet) would default storage_dir to
        # the global DF_INFRA_STORAGE_DIR and silently inherit an unrelated installation's
        # config.json values.
        storage_dir = env_get(env_file, "DF_INFRA_STORAGE_DIR", should_raise=False) or str(DF_INFRA_STORAGE_DIR)
        config_json_settings = read_config_json_settings(Path(storage_dir) / "config.json")
        original_env_content = merge_config_json_into_env(original_env_content, config_json_settings)

    return InstallContext(resolved_template, directory, docker_socket, newest_image_tag, original_env_content)


def mergeable_field_names() -> frozenset[str]:
    """Names of the `_MERGEABLE_FIELDS` keys.

    Lets the Typer command compute which of them were genuinely passed on the command line (via
    `ctx.get_parameter_source()`), rather than merely having a same-named parameter that happens to
    hold its own default value.
    """
    return frozenset(key for key, _ in _MERGEABLE_FIELDS)


@dataclass
class InstallConfig:
    """Final, fully-resolved installation values, ready to be persisted."""

    directory: Path
    docker_socket: str
    df_name: str
    infra_url: str
    infra_port: int
    df_infra_image: str
    docker_network: str
    docker_config: Path
    admin_api_key: str
    api_key: str
    mesh_key: str
    compose_prefix: str
    storage_dir: Path
    metrics_username: str
    metrics_password: str
    hugging_face_token: str | None
    civitai_token: str | None
    local_image: bool
    print_keys: bool
    df_connect_to_mesh_url: str | None
    df_connect_to_mesh_key: str | None


# (template config key, matching key in a prior install's .env)
_MERGEABLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("port", "df_infra_port"),
    ("infra_name", "df_name"),
    ("infra_url", "df_infra_url"),
    ("docker_network", "df_infra_docker_subnet"),
)


def _resolve_port(port: int, original_env_content: EnvDict, explicitly_provided: Collection[str]) -> int:
    """Restore a prior install's port unless explicitly overridden - regardless of --template.

    port has no prompt of its own to restore a prior value via a `default=` the way the other
    _MERGEABLE_FIELDS do, so this must run unconditionally, not just when a template happens to
    also set `port` (unlike _merge_template_config's per-key loop, gated on template_config).

    Raises:
        InstallError: If a prior install's .env has a non-numeric DF_INFRA_PORT value.
    """
    if "port" in explicitly_provided:
        return port
    prior_value = original_env_content.get("df_infra_port")
    if not prior_value:
        return port
    try:
        return int(str(prior_value))
    except ValueError:
        raise InstallError(
            f"Existing .env has an invalid DF_INFRA_PORT value ({prior_value!r}); fix or remove it before retrying."
        ) from None


def _merge_template_config(
    template_config: dict[str, Any],
    original_env_content: EnvDict,
    values: dict[str, Any],
    explicitly_provided: Collection[str],
) -> tuple[dict[str, Any], set[str], set[str]]:
    """Fill in CLI-level install values from a template's config, without overriding what should win.

    Precedence, highest to lowest: an explicit CLI flag (its key is in `explicitly_provided`) always
    wins; a value already configured by a prior install (found in that install's .env) is preserved
    next - a template must not silently discard existing configuration; only then does the
    template's config value apply; the CLI option's hardcoded default is the fallback.

    Args:
        template_config: The resolved template's "config" mapping (empty if no template was given).
        original_env_content: The prior install's .env content, merged with config.json (empty if
            neither existed).
        values: CLI-resolved values for the fields in `_MERGEABLE_FIELDS`, keyed by their template
            config key, e.g. {"port": port, "infra_name": infra_name, ...}. `port` must already be
            resolved via `_resolve_port()` before calling this - unlike the other fields, it has no
            prompt of its own to restore a prior `.env` value via a `default=`, so for `port` this
            loop only *blocks* the template from overriding the already-restored value in `values`;
            it never restores one into it itself. For `infra_name`/`infra_url`/`docker_network`,
            this loop instead blocks the template from claiming the slot at all, leaving the CLI
            value in place so the field's own prompt (in `resolve()`) can still restore a prior
            `.env` value afterward via its `default=`.
        explicitly_provided: The subset of `_MERGEABLE_FIELDS` keys whose CLI option was actually
            passed on the command line or via its envvar for this invocation - computed by the
            Typer command from `ctx.get_parameter_source()`, not by comparing `values` against each
            field's own default (which can't tell an explicitly-passed flag from an unpassed one
            when the two happen to be equal).

    Returns:
        The merged values (same keys as `values`; every non-port field already holds its final
        resolved value once its key is in either of the two returned sets - restored directly from
        the prior install's value when blocked by one; `port` is excluded from this restoration
        since it's already been resolved via `_resolve_port()` before this function is even
        called - see the `values` note above). The subset of `values`' keys that came from the
        template. And the subset that were blocked by a prior install's value, so `resolve()` can
        warn about each one instead of discarding it silently. `resolve()` passes
        force_provided=True for infra_name/infra_url/docker_network's prompt whenever the key is in
        *either* set, so an already-resolved value - whether from the template or from a prior
        install - isn't re-asked for; `port` has no prompt of its own, so its merged value (already
        resolved via `_resolve_port()`) is used as-is regardless.
    """
    merged = dict(values)
    from_template: set[str] = set()
    blocked_by_prior_value: set[str] = set()

    for key, env_key in _MERGEABLE_FIELDS:
        if key not in template_config:
            continue
        if key in explicitly_provided:
            continue  # an explicit CLI flag already wins

        prior_value = original_env_content.get(env_key)
        if prior_value:
            blocked_by_prior_value.add(key)
            if key != "port":
                merged[key] = prior_value
            continue  # a prior install's value must not be silently discarded

        merged[key] = template_config[key]
        from_template.add(key)

    return merged, from_template, blocked_by_prior_value


def resolve(
    context: InstallContext,
    *,
    port: int,
    image: str,
    docker_config: Path,
    storage: Path,
    hugging_face_token: str | None,
    civitai_token: str | None,
    infra_name: str,
    infra_url: str,
    docker_network: str,
    local_image: bool,
    allow_print_keys: bool | None,
    keep_compose_prefix: bool | None,
    keep_storage: bool | None,
    keep_metrics: bool | None,
    explicitly_provided: Collection[str] = frozenset(),
) -> InstallConfig:
    """Prompt the user for / apply CLI overrides to the remaining install values.

    `port` is first restored from a prior install's `.env` unconditionally via `_resolve_port()`
    (regardless of whether a `--template` was given, and regardless of whether it declares `port`),
    which can raise `InstallError` on a malformed prior value. The result then feeds into
    `_merge_template_config()` along with infra_name/infra_url/docker_network, which merges in
    `context.resolved_template`'s config for all four: an explicit CLI flag always wins, a value
    already configured by a prior install (found in `context.original_env_content`) is preserved
    next, and only then does the template's config value apply. See `_resolve_port()` and
    `_merge_template_config()`.

    Args:
        context: Read-only values gathered by :func:`inspect`, including any resolved --template.
        port: Published port to serve the DeepFellow Infra from.
        image: DeepFellow Infra docker image, before newest-tag resolution.
        docker_config: Path to the docker config file.
        storage: Storage directory for the DeepFellow Infra services.
        hugging_face_token: Optional Hugging Face token.
        civitai_token: Optional Civitai token.
        infra_name: Requested DF_NAME.
        infra_url: Requested DF_INFRA_URL.
        docker_network: Requested docker network name.
        local_image: Whether a locally built docker image is used.
        allow_print_keys: Whether to print API keys to the console.
        keep_compose_prefix: Whether to keep a previously configured compose prefix.
        keep_storage: Whether to keep a previously configured storage dir.
        keep_metrics: Whether to keep previously configured metrics credentials.
        explicitly_provided: The subset of `_MERGEABLE_FIELDS` keys actually passed on the command
            line or via envvar for this invocation - see `_merge_template_config()`. Defaults to
            empty for callers outside a Typer invocation (e.g. tests), which means every field is
            treated as not explicit.

    Returns:
        InstallConfig: The fully-resolved installation configuration.

    Raises:
        InstallError: If a prior install's .env has a non-numeric port value (via `_resolve_port()`).
    """
    original_env_content = context.original_env_content
    port = _resolve_port(port, original_env_content, explicitly_provided)

    template_config = context.resolved_template["config"] if context.resolved_template else {}
    merged, from_template, blocked_by_prior_value = _merge_template_config(
        template_config,
        original_env_content,
        {"port": port, "infra_name": infra_name, "infra_url": infra_url, "docker_network": docker_network},
        explicitly_provided,
    )
    for key in blocked_by_prior_value:
        echo.warning(f"Template's '{key}' config value is ignored because a prior install already configured it.")
    # A value already resolved - whether supplied by the template or restored from a prior
    # install - must not be re-asked for downstream; see _merge_template_config()'s Returns.
    already_resolved = from_template | blocked_by_prior_value
    port, infra_name, infra_url, docker_network = (
        merged["port"],
        merged["infra_name"],
        merged["infra_url"],
        merged["docker_network"],
    )

    df_name = echo.prompt(
        "Provide a DF_NAME for this Infra",
        validation=validate_df_name,
        from_args=infra_name,
        original_default=DF_INFRA_NAME,
        default=original_env_content.get("df_name", infra_name),
        force_provided="infra_name" in already_resolved,
    )

    df_infra_url = echo.prompt_until_valid(
        "Provide a DF_INFRA_URL for this Infra",
        validate_url,
        error_message="Invalid DF_INFRA_URL. Please try again.",
        from_args=infra_url,
        original_default=DF_INFRA_URL,
        default=original_env_content.get("df_infra_url", infra_url),
        force_provided="infra_url" in already_resolved,
    )

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
        force_provided="docker_network" in already_resolved,
    )

    flag_print_keys = echo.confirm("Is it safe to print API keys here?", from_args=allow_print_keys)

    # Collect DF_INFRA_ADMIN_API_KEY
    echo.info("Configuration of DF_INFRA_ADMIN_API_KEY\nkey required for an admin identify in DeepFellow Infra.")
    admin_api_key = configure_uuid_key("DF_INFRA_ADMIN_API_KEY", original_env_content.get("df_infra_admin_api_key"))
    if flag_print_keys:
        echo.info(f"DF_INFRA_ADMIN_API_KEY: {admin_api_key}")

    # Collect DF_INFRA_API_KEY
    echo.info(
        "Configuration of DF_INFRA_API_KEY\nkey needed to communication between DeepFellow Infra and DeepFellow Server."
    )
    api_key = configure_uuid_key("DF_INFRA_API_KEY", original_env_content.get("df_infra_api_key"))
    if flag_print_keys:
        echo.info(f"DF_INFRA_API_KEY: {api_key}")

    # Collect DF_MESH_KEY
    echo.info(
        "Configuration of DF_MESH_KEY\n"
        "key needed by other DeepFellow Infra to attach to this DeepFellow Infra and thus extend the Mesh."
    )
    mesh_key = configure_uuid_key("DF_MESH_KEY", original_env_content.get("df_mesh_key"))
    if flag_print_keys:
        echo.info(f"DF_MESH_KEY: {mesh_key}")

    # Find out the compose prefix
    original_compose_prefix = original_env_content.get("df_infra_compose_prefix")
    if original_compose_prefix is not None and echo.confirm(
        f"Would you like to keep the previously configured compose prefix '{original_compose_prefix}'?",
        from_args=keep_compose_prefix,
        default=True,
    ):
        compose_prefix = str(original_compose_prefix)
    else:
        random_letters = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        compose_prefix = f"df{random_letters}_"

    # Find out the infra storage dir
    original_storage_raw = original_env_content.get("df_infra_storage_dir")
    original_storage: Path | None = Path(str(original_storage_raw)) if original_storage_raw is not None else None
    if (
        original_storage is not None
        and original_storage != DF_INFRA_STORAGE_DIR
        and storage == DF_INFRA_STORAGE_DIR
        and echo.confirm(
            f"Would you like to keep the previously configured storage dir '{original_storage}'?",
            from_args=keep_storage,
            default=True,
        )
    ):
        storage = original_storage

    original_metrics_username = original_env_content.get("df_metrics_username")
    original_metrics_password = original_env_content.get("df_metrics_password")

    if (
        original_metrics_username is not None
        and original_metrics_password is not None
        and echo.confirm(
            "Would you like to keep the previously configured metrics credentials?",
            from_args=keep_metrics,
            default=True,
        )
    ):
        metrics_username = str(original_metrics_username)
        metrics_password = str(original_metrics_password)
    else:
        metrics_username = generate_password(8)
        metrics_password = generate_password(12)

    hugging_face_token = hugging_face_token or echo.prompt(
        "Provide an optional Hugging Face Token",
        from_args=hugging_face_token,
        original_default=None,
        default=original_env_content.get("df_hugging_face_token", hugging_face_token) or "",
        password=True,
    )

    civitai_token = civitai_token or echo.prompt(
        "Provide an optional Civitai Token",
        from_args=civitai_token,
        original_default=None,
        default=original_env_content.get("df_civitai_token", civitai_token) or "",
        password=True,
    )

    return InstallConfig(
        directory=context.directory,
        docker_socket=context.docker_socket,
        df_name=df_name,
        infra_url=df_infra_url,
        infra_port=port,
        df_infra_image=context.newest_image_tag or image,
        docker_network=docker_network,
        docker_config=docker_config,
        admin_api_key=admin_api_key,
        api_key=api_key,
        mesh_key=mesh_key,
        compose_prefix=compose_prefix,
        storage_dir=storage,
        metrics_username=metrics_username,
        metrics_password=metrics_password,
        hugging_face_token=hugging_face_token or None,
        civitai_token=civitai_token or None,
        local_image=local_image,
        print_keys=flag_print_keys,
        df_connect_to_mesh_url=None,
        df_connect_to_mesh_key=None,
    )


def apply(config: InstallConfig, will_auto_start: bool = False) -> None:
    """Create the docker network, write the .env/compose files, and pull the image.

    Purely programmatic: no prompts, so it does not leave a half-configured
    installation behind if an earlier phase (:func:`resolve`) was interrupted.

    Args:
        config: The fully-resolved installation configuration.
        will_auto_start: Whether the caller is about to start infra itself right after (a
            template with post_start_actions) - changes the success message so it doesn't tell
            the user to run `infra start` when that's about to happen automatically.
    """
    config_file = state.cli_config_file
    secrets_file = state.cli_secrets_file

    # Create empty docker config if needed
    if not config.docker_config.is_file():
        try:
            config.docker_config.write_text("{}", encoding="utf-8")
        except OSError as exc:
            echo.error(str(exc))
            raise typer.Exit(1) from exc

    # Create the network if needed
    ensure_network(config.docker_network)

    # Save the envs to the .env file (existing envs are NOT overwritten)
    infra_values: dict[str, str | int] = {
        "DF_NAME": config.df_name,
        "DF_INFRA_URL": config.infra_url,
        "DF_INFRA_PORT": config.infra_port,
        "DF_INFRA_IMAGE": config.df_infra_image,
        "DF_MESH_KEY": config.mesh_key,
        "DF_INFRA_API_KEY": config.api_key,
        "DF_INFRA_ADMIN_API_KEY": config.admin_api_key,
        "DF_CONNECT_TO_MESH_URL": config.df_connect_to_mesh_url or "",
        "DF_CONNECT_TO_MESH_KEY": config.df_connect_to_mesh_key or "",
        "DF_INFRA_DOCKER_SUBNET": config.docker_network,
        "DF_INFRA_COMPOSE_PREFIX": config.compose_prefix,
        "DF_INFRA_DOCKER_CONFIG": str(config.docker_config),
        "DF_INFRA_STORAGE_DIR": config.storage_dir.expanduser().resolve().as_posix(),
        "DF_METRICS_USERNAME": config.metrics_username,
        "DF_METRICS_PASSWORD": config.metrics_password,
    }
    if config.hugging_face_token:
        infra_values["DF_HUGGING_FACE_TOKEN"] = config.hugging_face_token
    if config.civitai_token:
        infra_values["DF_CIVITAI_TOKEN"] = config.civitai_token

    save_env_file(config.directory / ".env", infra_values)
    env_set(config_file, "DF_INFRA_EXTERNAL_URL", f"http://localhost:{config.infra_port}", should_raise=False)
    env_set(secrets_file, "DF_INFRA_ADMIN_API_KEY", config.admin_api_key, should_raise=False)

    # Save the docker compose config
    compose = deepcopy(DOCKER_COMPOSE_INFRA)
    infra_service = compose["infra"]
    add_network_to_service(infra_service, config.docker_network)

    volumes = cast("list", infra_service["volumes"])
    volumes.append(f"{config.docker_socket}:/run/docker.sock")
    volumes.append(f"{config.docker_socket}:/var/run/docker.sock")
    volumes.append("${DF_INFRA_STORAGE_DIR}:${DF_INFRA_STORAGE_DIR}")

    if config.local_image:
        infra_service["pull_policy"] = "never"

    save_compose_file(
        {"services": compose, "networks": {config.docker_network: {"external": True}}},
        config.directory / DOCKER_COMPOSE_CONFIG_FILENAME,
    )

    echo.info("Pulling docker image(s).")
    try:
        run(["docker", "compose", "pull"], config.directory, raises=DockerError)
    except DockerError as exc:
        echo.error(f"Failed to pull docker image(s): {exc}\nCheck registry access, credentials, and disk space.")
        raise typer.Exit(1) from exc
    start_hint = (
        "Starting it now to run the template's post-start actions."
        if will_auto_start
        else "To start the docker image - `deepfellow infra start`."
    )
    echo.success(f"DeepFellow Infra installed.\n{start_hint}\nFor info about installation - `deepfellow infra info`.")


@translate_to_install_error
def _prepare_post_start_action(action: PostStartAction) -> Callable[[], None]:
    """Run whatever of a post-start action's ask/build phase can run now, returning its apply phase.

    `infra.model.install`'s build phase only resolves an infra connection (which may prompt for a
    URL and/or an admin API key), and `infra.service.install`'s build phase resolves that same
    connection plus the service's install spec (which may prompt for individual spec fields, driven
    by a field list fetched from the already-running infra's API) - both are hoisted here, leaving
    only the install API call itself in the returned callable. Every other (currently hypothetical)
    action is deferred whole to the returned callable and dispatched as one, exactly as before.

    Args:
        action: The post-start action to prepare, with its kwargs already finalized by the caller.

    Returns:
        A zero-argument callable performing `action`'s apply phase.

    Raises:
        InstallError: If the action's build phase fails (translated from typer.Exit and friends by
            the decorator). Any other exception type raised by the build phase propagates unmodified.
    """
    if action["function"] == "infra.model.install":
        kwargs = dict(action["kwargs"])
        connection = resolve_model_connection(kwargs.pop("server", None))
        apply_phase: Callable[[], None] = partial(apply_model_install, connection=connection, **kwargs)
    elif action["function"] == "infra.service.install":
        kwargs = dict(action["kwargs"])
        name = kwargs.pop("name")
        quiet = kwargs.pop("quiet", False)
        install_spec = build_service_spec(name, **kwargs)
        apply_phase = partial(apply_service_spec, name, install_spec, quiet=quiet or not install_spec.explicit_spec)
    else:
        apply_phase = partial(dispatch_post_start_action, action)

    # The apply pass reports one InstallError per action; without this, a typer.Exit raised by a
    # worker called directly (rather than through dispatch_post_start_action, which translates it
    # itself) would escape to install()'s own @translate_to_install_error and lose that context.
    return translate_to_install_error(apply_phase)


def _run_post_start_actions(post_start_actions: list[PostStartAction], infra_port: int) -> None:
    """Run a template's post-start actions: every action's ask phase first, then every apply phase.

    Args:
        post_start_actions: The resolved template's post-start actions, run in list order. Their
            kwargs are finalized in place (see the "server" injection below).
        infra_port: The port infra was actually installed on, used to build the localhost URL every
            action is pointed at.

    Raises:
        typer.Exit: If any action's build or apply phase fails.
    """
    infra_localhost_url = f"http://localhost:{infra_port}"
    total = len(post_start_actions)

    # Ask-phase pass: this loop itself only finalizes each action's kwargs (no prompting) and then
    # hands it to _prepare_post_start_action(), which does the asking - so everything that can be
    # asked up front is, before any action's apply phase runs, and a failure partway through the
    # apply pass below never wastes an answer the user has yet to give. See
    # _prepare_post_start_action() for the one action kind whose build phase can't be hoisted.
    apply_phases: list[Callable[[], None]] = []
    for index, action in enumerate(post_start_actions, start=1):
        template_server = action["kwargs"].get("server")
        if template_server is not None and template_server != infra_localhost_url:
            echo.warning(
                f"Post-start action {index}/{total} ('{action['function']}') set its own "
                f"'server' ({template_server!r}); overriding it with the actually-installed "
                f"infra's address ({infra_localhost_url!r})."
            )
        action["kwargs"]["server"] = infra_localhost_url
        try:
            apply_phases.append(_prepare_post_start_action(action))
        except InstallError as exc:
            echo.error(
                f"Post-start action {index}/{total} ('{action['function']}') could not be prepared: {exc}\n"
                "Infra is already installed and running; no post-start action has run yet."
            )
            raise typer.Exit(1) from exc
        except Exception as exc:
            # See the apply pass below for why a second, broader handler is needed.
            echo.error(
                f"Post-start action {index}/{total} ('{action['function']}') could not be prepared "
                f"due to an unexpected failure: {exc}\n"
                "Infra is already installed and running; no post-start action has run yet."
            )
            raise typer.Exit(1) from exc

    # Apply-phase pass: no prompting left, only the actions' actual effects.
    for index, (action, apply_phase) in enumerate(zip(post_start_actions, apply_phases, strict=True), start=1):
        try:
            apply_phase()
        except InstallError as exc:
            echo.error(
                f"Post-start action {index}/{total} ('{action['function']}') failed: {exc}\n"
                f"Infra is already installed and running; {index - 1} of {total} action(s) "
                "completed before this failure."
            )
            raise typer.Exit(1) from exc
        except Exception as exc:
            # An apply phase only translates typer.Exit/BadParameter/Docker/OSError failures
            # into InstallError (see deepfellow.common.exceptions.translate_to_install_error);
            # any other exception type propagates unmodified. Catch it here too, so a future
            # post-start action that raises outside that translated set still gets the same
            # operator-facing message instead of a bare traceback.
            echo.error(
                f"Post-start action {index}/{total} ('{action['function']}') failed unexpectedly: {exc}\n"
                f"Infra is already installed and running; {index - 1} of {total} action(s) "
                "completed before this failure."
            )
            raise typer.Exit(1) from exc


@translate_to_install_error
def install(
    directory: Path = DF_INFRA_DIRECTORY,
    port: int = DF_INFRA_PORT,
    image: str = DF_INFRA_IMAGE,
    local_image: bool = False,
    docker_config: Path | None = None,
    storage: Path = DF_INFRA_STORAGE_DIR,
    hugging_face_token: str | None = None,
    civitai_token: str | None = None,
    infra_name: str = DF_INFRA_NAME,
    infra_url: str = DF_INFRA_URL,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    template: str | None = None,
    force_install: bool = False,
    allow_rootful: bool = False,
    allow_print_keys: bool | None = None,
    keep_compose_prefix: bool | None = None,
    keep_storage: bool | None = None,
    keep_metrics: bool | None = None,
    explicitly_provided: Collection[str] = frozenset(),
) -> None:
    """Install infra with docker."""
    # Retrieve the docker info to fail early in the process in docker is not running or configured differently
    echo.info("Installing DeepFellow Infra.")

    context = inspect(
        directory=directory,
        allow_rootful=allow_rootful,
        force_install=force_install,
        image=image,
        local_image=local_image,
        template=template,
    )

    docker_config = docker_config or directory / "docker-config.json"

    config = resolve(
        context,
        port=port,
        image=image,
        docker_config=docker_config,
        storage=storage,
        hugging_face_token=hugging_face_token,
        civitai_token=civitai_token,
        infra_name=infra_name,
        infra_url=infra_url,
        docker_network=docker_network,
        local_image=local_image,
        allow_print_keys=allow_print_keys,
        keep_compose_prefix=keep_compose_prefix,
        keep_storage=keep_storage,
        keep_metrics=keep_metrics,
        explicitly_provided=explicitly_provided,
    )

    post_start_actions = context.resolved_template["post_start_actions"] if context.resolved_template else []
    apply(config, will_auto_start=bool(post_start_actions))

    if post_start_actions:
        try:
            start_infra(directory)
        except (DockerNetworkError, typer.Exit) as exc:
            reason = str(exc) if isinstance(exc, DockerNetworkError) else "see console output above for details."
            echo.error(f"Failed to start infra for template post-start actions: {reason}")
            raise typer.Exit(1) from exc

        # The CLI process runs outside Docker, so post-start actions must reach infra via
        # localhost on the port actually resolved above - never a template-supplied "server",
        # which could only ever guess at that port.
        _run_post_start_actions(post_start_actions, config.infra_port)
