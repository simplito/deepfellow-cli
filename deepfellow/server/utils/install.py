# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Install server core logic."""

import json
from collections.abc import Collection
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import typer

from deepfellow.common.config import (
    EnvDict,
    merge_config_json_into_env,
    read_config_json_settings,
    read_env_file_to_dict,
    save_env_file,
)
from deepfellow.common.defaults import (
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_FALKORDB_URL,
    DF_INFRA_DIRECTORY,
    DF_INFRA_DOCKER_NETWORK,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DF_SERVER_DIRECTORY,
    DF_SERVER_IMAGE,
    DF_SERVER_IMAGE_HUB,
    DF_SERVER_PORT,
    DF_SERVER_STORAGE_DIRECTORY,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    DOCKER_COMPOSE_MILVUS,
    DOCKER_COMPOSE_MONGO_DB,
    DOCKER_COMPOSE_QDRANT,
    DOCKER_COMPOSE_SERVER,
    DOCKER_COMPOSE_SERVER_FALKORDB_ENVS,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS,
    DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS,
    MILVUS_DATABASE,
    VectorDBTypeChoice,
)
from deepfellow.common.docker import (
    DockerError,
    add_network_to_service,
    ensure_network,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get
from deepfellow.common.exceptions import DockerNetworkError, InstallError, reraise_if_debug, translate_to_install_error
from deepfellow.common.generate import generate_password
from deepfellow.common.install import (
    assert_docker,
    ensure_directory,
    resolve_admin_kwargs,
    validate_non_interactive_admin_values,
)
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.system import run
from deepfellow.common.templates import InstallTemplate
from deepfellow.server.utils.configure import (
    FalkorDBConfig,
    OtelConfig,
    configure_falkordb,
    configure_infra,
    configure_mongo,
    configure_otel,
    configure_vector_db,
)
from deepfellow.server.utils.docker import start_server
from deepfellow.server.utils.templates import dispatch_post_start_action, resolve_template

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

# (template config key, path of keys to a prior install's value in original_env_content). Server's
# .env is read back as a *nested* dict (env_to_dict splits keys on "__"), unlike infra's flat one -
# most of these fields live 2-3 levels deep, e.g. vectordb_url is at
# original_env_content["df_vector_database"]["provider"]["url"], not a flat
# "df_vector_database_provider_url" key. Only port and docker_network are written as plain
# single-underscore keys and stay flat.
_MERGEABLE_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("port", ("df_server_port",)),
    ("docker_network", ("df_infra_docker_subnet",)),
    ("infra_url", ("df_infra", "url")),
    ("infra_api_key", ("df_infra", "api_key")),
    ("vectordb_url", ("df_vector_database", "provider", "url")),
    ("vectordb_database_name", ("df_vector_database", "provider", "db")),
    ("embedding_model", ("df_vector_database", "embedding", "model")),
    ("embedding_size", ("df_vector_database", "embedding", "size")),
    ("vectordb_type", ("df_vector_database", "provider", "type")),
)


def _is_json_object(value: str) -> bool:
    """Check whether a string parses as a JSON object.

    Args:
        value: The string to parse.

    Returns:
        True if the value is valid JSON with an object at the top level.
    """
    try:
        return isinstance(json.loads(value), dict)
    except (ValueError, TypeError, RecursionError):
        return False


def expose_ports_to_host(services: dict[str, Any]) -> None:
    """Add host port mappings for services that only have 'expose' (no 'ports')."""
    for service in services.values():
        if "expose" in service and "ports" not in service:
            service["ports"] = [f"{port}:{port}" for port in service["expose"]]


@dataclass
class InstallContext:
    """Read-only values gathered from the environment before any prompting."""

    resolved_template: InstallTemplate | None
    directory: Path
    newest_image_tag: str | None
    original_env_content: EnvDict
    log_level: str
    plugins_setup: str


def _validate_non_interactive_post_start_actions(
    resolved_template: InstallTemplate,
    admin_name: str | None,
    admin_email: str | None,
    admin_password: str | None,
) -> None:
    """Fail fast if --non-interactive can't run a template's post-start actions without prompting.

    server.create_admin prompts for whichever of name/email/password is falsy; under
    --non-interactive there's no prompt to fall back on and it would raise typer.Exit(1) after the
    server is already installed and started. Catching that here, before inspect()'s Docker/filesystem
    side effects, gives a clear error instead of a failure partway through a successful install.

    Args:
        resolved_template: The resolved template whose post_start_actions to check.
        admin_name: CLI-provided admin name override, if any.
        admin_email: CLI-provided admin email override, if any.
        admin_password: CLI-provided admin password override, if any.

    Raises:
        InstallError: If --non-interactive is set and a server.create_admin action is missing
            name, email, or password.
    """
    for action in resolved_template["post_start_actions"]:
        if action["function"] != "server.create_admin":
            continue
        effective = resolve_admin_kwargs(action["kwargs"], admin_name, admin_email, admin_password)
        validate_non_interactive_admin_values(effective, "Template's 'server.create_admin' post-start action")


def inspect(
    directory: Path,
    image: str,
    local_image: bool,
    force_install: bool,
    template: str | None = None,
    admin_name: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
) -> InstallContext:
    """Resolve --template, then do a Docker check, directory creation, and existing .env read-back.

    Resolves and validates `template` (via resolve_template()), if given, before touching Docker or
    the filesystem, so a bad template - or one that --non-interactive can't complete - fails fast
    without side effects. No prompts, no network/compose writes.

    Returns:
        InstallContext: Read-only values needed by :func:`resolve`.

    Raises:
        InstallError: If `template` is not a known built-in name or a valid, readable YAML file
            matching the expected schema (see resolve_template()); or if --non-interactive is set
            and a resolved post-start action would need to prompt (see
            _validate_non_interactive_post_start_actions()).
    """
    resolved_template = None
    if template is not None:
        resolved_template = resolve_template(template)
        _validate_non_interactive_post_start_actions(resolved_template, admin_name, admin_email, admin_password)

    assert_docker()
    ensure_directory(
        directory, error_message="Unable to create DeepFellow Server directory.", force_install=force_install
    )
    newest_image_tag = (
        get_newest_image_tag(DF_SERVER_IMAGE_HUB) if not local_image and image == DF_SERVER_IMAGE else None
    )

    env_file = directory / ".env"
    original_env_content: EnvDict = read_env_file_to_dict(env_file)
    if env_file.is_file():
        # Only read config.json once a prior .env is confirmed for this directory - otherwise a
        # fresh install (no .env yet) would silently inherit config.json values left behind by any
        # other server install that ever used the same global DF_SERVER_STORAGE_DIRECTORY.
        config_json_settings = read_config_json_settings(DF_SERVER_STORAGE_DIRECTORY / "config.json")
        original_env_content = merge_config_json_into_env(original_env_content, config_json_settings)

    log_level = str(original_env_content.get("df_log_level", "INFO")).upper()
    if log_level not in LOG_LEVELS:
        echo.error(f"Invalid DF_LOG_LEVEL in {env_file.as_posix()}: expected one of {', '.join(LOG_LEVELS)}.")
        raise typer.Exit(1)

    plugins_setup = original_env_content.get("df_plugins_setup", "{}")
    if not isinstance(plugins_setup, str) or not _is_json_object(plugins_setup):
        echo.error(f"Invalid DF_PLUGINS_SETUP in {env_file.as_posix()}: expected a single-line JSON object.")
        raise typer.Exit(1)

    return InstallContext(
        resolved_template,
        directory,
        newest_image_tag,
        original_env_content,
        log_level,
        plugins_setup,
    )


def mergeable_field_names() -> frozenset[str]:
    """Names of the `_MERGEABLE_FIELDS` keys.

    Lets the Typer command compute which of them were genuinely passed on the command line (via
    `ctx.get_parameter_source()`), rather than merely having a same-named parameter that happens to
    hold its own default value.
    """
    return frozenset(key for key, _ in _MERGEABLE_FIELDS)


def _get_nested_env_value(original_env_content: EnvDict, path: tuple[str, ...]) -> Any:
    """Walk a _MERGEABLE_FIELDS path into a nested EnvDict, returning None if any segment is missing.

    Args:
        original_env_content: The prior install's .env content, as read back by read_env_file_to_dict
            and merged with config.json's settings by merge_config_json_into_env() (nested on "__"
            boundaries).
        path: The key path to walk, e.g. ("df_vector_database", "provider", "url").

    Returns:
        The value at that path, or None if any segment along the way is absent or not a dict (e.g.
        vectordb_database_name's path is only ever populated for a milvus install - a prior qdrant
        install has no "db" key to find, which correctly reads back as None here, not an error).
    """
    node: Any = original_env_content
    for segment in path:
        if not isinstance(node, dict):
            return None
        node = node.get(segment)
    return node


def _resolve_port(port: int, original_env_content: EnvDict, explicitly_provided: Collection[str]) -> int:
    """Restore a prior install's port unless explicitly overridden - regardless of --template.

    port has no prompt of its own to restore a prior value via a `default=` the way the other
    _MERGEABLE_FIELDS do, so this must run unconditionally, not just when a template happens to
    also set `port` (unlike _merge_template_config's per-key loop, gated on template_config).

    Raises:
        InstallError: If a prior install's .env has a non-numeric DF_SERVER_PORT value.
    """
    if "port" in explicitly_provided:
        return port
    prior_value = _get_nested_env_value(original_env_content, ("df_server_port",))
    if prior_value is None:
        return port
    try:
        return int(str(prior_value))
    except ValueError:
        raise InstallError(
            f"Existing .env has an invalid DF_SERVER_PORT value ({prior_value!r}); fix or remove it before retrying."
        ) from None


def _merge_template_config(
    template_config: dict[str, Any],
    original_env_content: EnvDict,
    values: dict[str, Any],
    explicitly_provided: Collection[str],
) -> tuple[dict[str, Any], set[str], set[str]]:
    """Fill in CLI-level install values from a template's config, without overriding what should win.

    Precedence, highest to lowest: an explicit CLI flag (its key is in `explicitly_provided`) always
    wins; a value already configured by a prior install (found in that install's `.env`, merged with
    any `config.json` values by `merge_config_json_into_env()` before `original_env_content` reaches
    here) is preserved next - a template must not silently discard existing configuration; only then
    does the template's config value apply; the CLI option's hardcoded default is the fallback.

    Args:
        template_config: The resolved template's "config" mapping (empty if no template was given).
        original_env_content: The prior install's .env content, merged with config.json (empty if
            neither existed).
        values: CLI-resolved values for the fields in `_MERGEABLE_FIELDS`, keyed by their template
            config key, e.g. {"port": port, "docker_network": docker_network, ...}. `port` must
            already be resolved via `_resolve_port()` before calling this - unlike the other
            fields, it has no prompt of its own to restore a prior `.env` value via a `default=`,
            so this loop only *blocks* the template from overriding a prior value that's already
            in `values`; it never restores one into it.
        explicitly_provided: The subset of `_MERGEABLE_FIELDS` keys whose CLI option was actually
            passed on the command line or via its envvar for this invocation - computed by the
            Typer command from `ctx.get_parameter_source()`, not by comparing `values` against each
            field's own default (which can't tell an explicitly-passed flag from an unpassed one
            when the two happen to be equal).

    Returns:
        The merged values (same keys as `values`). The subset of `values`' keys that came from the
        template (`resolve()` passes force_provided=True (docker_network's own prompt) or the
        matching force_provided_* kwarg (configure_infra()/configure_vector_db(), for the other
        seven prompted fields) whenever the key is in this set, so a template-supplied value isn't
        re-asked for even when it equals that field's own default). And the subset of
        template_config's keys that were ignored because a prior install already set that field, so
        `resolve()` can warn about each one instead of discarding it silently.
    """
    merged = dict(values)
    from_template: set[str] = set()
    blocked_by_prior_value: set[str] = set()

    for key, path in _MERGEABLE_FIELDS:
        if key not in template_config:
            continue
        if key in explicitly_provided:
            continue  # an explicit CLI flag already wins

        prior_value = _get_nested_env_value(original_env_content, path)
        if prior_value is not None:
            blocked_by_prior_value.add(key)
            continue  # a prior install's value must not be silently discarded

        merged[key] = template_config[key]
        from_template.add(key)

    return merged, from_template, blocked_by_prior_value


@dataclass
class InstallConfig:
    """Final, fully-resolved installation values, ready to be persisted."""

    directory: Path
    port: int
    image: str
    docker_network: str
    log_level: str
    plugins_setup: str
    metrics_username: str
    metrics_password: str
    mongo_env: dict[str, str]
    custom_mongo_db_server: bool
    infra_env: dict[str, Any]
    vectordb_envs: dict[str, str]
    is_vectordb_active: bool
    is_custom_vector_db_server: bool
    vectordb_type: str
    otel: OtelConfig
    falkordb: FalkorDBConfig
    local_image: bool
    dev: bool


def resolve(
    context: InstallContext,
    *,
    port: int,
    image: str,
    otel_url: str | None,
    otel_local: bool,
    infra_url: str,
    infra_api_key: str | None,
    docker_network: str,
    mongodb_url: str,
    mongodb_port: int,
    mongodb_database_name: str,
    mongodb_username: str,
    mongodb_password: str,
    vectordb_active: bool,
    vectordb_type: VectorDBTypeChoice,
    vectordb_url: str,
    vectordb_database_name: str,
    vectordb_username: str,
    vectordb_password: str,
    embedding_model: str,
    embedding_size: str,
    embedding_sparse: bool,
    falkordb_active: bool,
    falkordb_url: str,
    falkordb_username: str,
    falkordb_password: str,
    local_image: bool,
    dev: bool,
    explicitly_provided: Collection[str] = frozenset(),
) -> InstallConfig:
    """Prompt the user for / apply CLI overrides to the remaining install values.

    Before prompting, restores a prior install's `port` via `_resolve_port()` (which has no prompt
    of its own to do this via a `default=`, unlike the other fields), then merges
    `context.resolved_template`'s config into the fields listed in `_MERGEABLE_FIELDS` via
    `_merge_template_config()`: an explicit CLI flag always wins, a value already configured by a
    prior install (found in `context.original_env_content`) is preserved next, and only then does
    the template's config value apply. See `_resolve_port()` and `_merge_template_config()`.

    Args:
        context: Read-only values gathered by :func:`inspect`, including any resolved --template.
        port: Published port to serve the DeepFellow Server from.
        image: DeepFellow Server docker image, before newest-tag resolution.
        otel_url: Existing Open Telemetry collector URL, if any.
        otel_local: Whether to install a local debug-only Open Telemetry collector.
        infra_url: DeepFellow Infra URL to connect to.
        infra_api_key: DeepFellow Infra API key. If not given, falls back to the `DF_INFRA_API_KEY`
            recorded in a local `infra install`'s own `.env` (`DF_INFRA_DIRECTORY / ".env"`), same as
            `suite install` does; stays `None` if that's not found either. That fallback is applied
            after the template merge below, not before, so a discovered local key doesn't outrank
            a template's own `infra_api_key` - it's a last resort, below even the template. It is
            also skipped entirely when a prior server install's `.env` already has its own
            `DF_INFRA__API_KEY`, so the local fallback never overwrites an already-configured
            server's infra connection.
        docker_network: Requested docker network name.
        mongodb_url: Requested MongoDB connection URL.
        mongodb_port: Host port to publish a locally managed MongoDB on.
        mongodb_database_name: Requested MongoDB database name.
        mongodb_username: Requested MongoDB username.
        mongodb_password: Requested MongoDB password.
        vectordb_active: Whether a vector database should be configured.
        vectordb_type: Requested vector database type.
        vectordb_url: Requested vector database connection URL.
        vectordb_database_name: Requested vector database database/collection name.
        vectordb_username: Requested vector database username.
        vectordb_password: Requested vector database password.
        embedding_model: Requested embedding model.
        embedding_size: Requested embedding size.
        embedding_sparse: Whether to use sparse embeddings.
        falkordb_active: Whether the Knowledge Graph's FalkorDB instance should be configured.
        falkordb_url: Requested FalkorDB connection host:port.
        falkordb_username: Requested FalkorDB username.
        falkordb_password: Requested FalkorDB password.
        local_image: Whether a locally built docker image is used.
        dev: Whether to expose internal service ports to the host.
        explicitly_provided: The subset of `_MERGEABLE_FIELDS` keys actually passed on the command
            line or via envvar for this invocation - see `_merge_template_config()`. Defaults to
            empty for callers outside a Typer invocation (e.g. tests), which means every field is
            treated as not explicit.

    Returns:
        InstallConfig: The fully-resolved installation configuration.
    """
    directory = context.directory
    original_env_content = context.original_env_content
    template_config = context.resolved_template["config"] if context.resolved_template else {}
    port = _resolve_port(port, original_env_content, explicitly_provided)

    merged, from_template, blocked_by_prior_value = _merge_template_config(
        template_config,
        original_env_content,
        {
            "port": port,
            "docker_network": docker_network,
            "infra_url": infra_url,
            "infra_api_key": infra_api_key,
            "vectordb_url": vectordb_url,
            "vectordb_database_name": vectordb_database_name,
            "embedding_model": embedding_model,
            "embedding_size": embedding_size,
            "vectordb_type": vectordb_type,
        },
        explicitly_provided,
    )
    for key in blocked_by_prior_value:
        echo.warning(f"Template's '{key}' config value is ignored because a prior install already configured it.")
    port = merged["port"]
    docker_network = merged["docker_network"]
    infra_url = merged["infra_url"]
    infra_api_key = merged["infra_api_key"]
    vectordb_url = merged["vectordb_url"]
    vectordb_database_name = merged["vectordb_database_name"]
    embedding_model = merged["embedding_model"]
    embedding_size = merged["embedding_size"]
    vectordb_type = merged["vectordb_type"]

    # Falls back to a local `infra install`'s own DF_INFRA_API_KEY only after the CLI flag/prior
    # server .env/template have all had a chance to supply one - done here, not before the merge
    # above, so a discovered local key isn't baked into values["infra_api_key"] and mistaken for
    # an explicit --infra-api-key flag there, which would silently (and without the warning every
    # other blocked field gets) block a template's own infra_api_key from ever applying. Also
    # skipped outright when a prior server .env already has its own api_key: infra_api_key would
    # otherwise still be None here (the merge above only *blocks* a template value from
    # overwriting it, it doesn't restore the prior value into this variable - that restoration
    # happens via configure_infra()'s own `default=` a few lines down), and feeding the local
    # fallback key into configure_infra() as `from_args` makes it look explicitly provided,
    # silently discarding the previously configured key.
    if not infra_api_key and not _get_nested_env_value(original_env_content, ("df_infra", "api_key")):
        infra_api_key = env_get(DF_INFRA_DIRECTORY / ".env", "DF_INFRA_API_KEY", should_raise=False)
        if infra_api_key:
            echo.warning("No DeepFellow Infra API key provided; using the key from a local `infra install`'s .env.")

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
        force_provided="docker_network" in from_template,
    )

    echo.info("DeepFellow Server requires a MongoDB to be installed.")
    if mongodb_url != DF_MONGO_URL or mongodb_database_name != DF_MONGO_DB:
        custom_mongo_db_server = True
    else:
        custom_mongo_db_server = not echo.confirm("Install a local MongoDB for DeepFellow Server?", default=True)

    mongo_env = configure_mongo(
        directory,
        custom_mongo_db_server,
        mongodb_username,
        mongodb_password,
        mongodb_url,
        mongodb_database_name,
        original_env_content,
        mongodb_port,
    )

    echo.info("DeepFellow Server is communicating with DeepFellow Infra.")
    infra_env = configure_infra(
        infra_api_key,
        infra_url,
        original_env_content,
        force_provided_url="infra_url" in from_template,
        force_provided_api_key="infra_api_key" in from_template,
    )

    original_metrics_username = original_env_content.get("df_metrics_username")
    original_metrics_password = original_env_content.get("df_metrics_password")

    if (
        original_metrics_username is not None
        and original_metrics_password is not None
        and echo.confirm("Would you like to keep the previously configured metrics credentials?", default=True)
    ):
        metrics_username = str(original_metrics_username)
        metrics_password = str(original_metrics_password)
    else:
        metrics_username = generate_password(8)
        metrics_password = generate_password(12)

    echo.info("DeepFellow Server might use a vector DB. If not provided some features will not work.")

    # Configure vector database
    is_custom_vector_db_server, vectordb_envs = configure_vector_db(
        infra_env["DF_INFRA__URL"],
        original_env_content,
        int(vectordb_active),
        vectordb_type.value,
        vectordb_url,
        vectordb_database_name,
        vectordb_username,
        vectordb_password,
        embedding_model,
        embedding_size,
        embedding_sparse,
        str(
            _get_nested_env_value(original_env_content, ("df_vector_database", "provider", "type"))
            or vectordb_type.value
        ),
        force_provided_type="vectordb_type" in from_template,
        force_provided_url="vectordb_url" in from_template,
        force_provided_database_name="vectordb_database_name" in from_template,
        force_provided_model="embedding_model" in from_template,
        force_provided_size="embedding_size" in from_template,
    )
    is_vectordb_active = vectordb_envs.get("DF_VECTOR_DATABASE__PROVIDER__ACTIVE") == "1"
    vectordb_type_str = vectordb_envs.get("DF_VECTOR_DATABASE__PROVIDER__TYPE", "")

    otel = configure_otel(directory, otel_url, original_env_content, otel_local)

    falkordb = configure_falkordb(
        falkordb_active, falkordb_url, falkordb_username, falkordb_password, original_env_content
    )

    return InstallConfig(
        directory=directory,
        port=port,
        image=context.newest_image_tag or image,
        docker_network=docker_network,
        log_level=context.log_level,
        plugins_setup=context.plugins_setup,
        metrics_username=metrics_username,
        metrics_password=metrics_password,
        mongo_env=mongo_env,
        custom_mongo_db_server=custom_mongo_db_server,
        infra_env=infra_env,
        vectordb_envs=vectordb_envs,
        is_vectordb_active=is_vectordb_active,
        is_custom_vector_db_server=is_custom_vector_db_server,
        vectordb_type=vectordb_type_str,
        otel=otel,
        falkordb=falkordb,
        local_image=local_image,
        dev=dev,
    )


def apply(config: InstallConfig, will_auto_start: bool = False) -> None:  # noqa: C901
    """Create the docker network, write the .env/compose files, and pull the image.

    Purely programmatic: no prompts, so it does not leave a half-configured
    installation behind if an earlier phase (:func:`resolve`) was interrupted.

    Args:
        config: The fully-resolved installation configuration.
        will_auto_start: Whether the caller is about to start server itself right after (a
            template with post_start_actions) - changes the success message so it doesn't tell
            the user to run `server start` when that's about to happen automatically.
    """
    # Create the network if needed
    ensure_network(config.docker_network)

    save_env_file(
        config.directory / ".env",
        {
            "DF_SERVER_PORT": config.port,
            "DF_SERVER_URL": f"http://localhost:{config.port}",
            "DF_SERVER_IMAGE": config.image,
            "DF_INFRA_DOCKER_SUBNET": config.docker_network,
            "DF_METRICS_USERNAME": config.metrics_username,
            "DF_METRICS_PASSWORD": config.metrics_password,
            "DF_LOG_LEVEL": config.log_level,
            "DF_PLUGINS_SETUP": config.plugins_setup,
            **config.mongo_env,
            **config.infra_env,
            **config.vectordb_envs,
            **config.otel.envs,
            **config.falkordb.envs,
        },
    )

    volumes: dict[str, None] = {}
    services: dict[str, Any] = {}
    depends_on = {}
    compose_server = deepcopy(DOCKER_COMPOSE_SERVER)
    # TODO Clean up the `cast` after https://gitlab2.simplito.com/df/df-cli/-/issues/258
    server_docker_envs = cast("list[str]", compose_server["server"]["environment"])

    if config.is_vectordb_active:
        # Update server's docker environment
        server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS)
        if config.vectordb_type == "milvus":
            server_docker_envs.extend(DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS)

        # Add vector database docker compose definitions if user did not provide custom fields
        if not config.is_custom_vector_db_server:
            if config.vectordb_type == "qdrant":
                services.update(deepcopy(DOCKER_COMPOSE_QDRANT))
                volumes.update({"qdrant_data": None})
                depends_on.update({"qdrant": {"condition": "service_started"}})
            else:
                services.update(deepcopy(DOCKER_COMPOSE_MILVUS))
                volumes.update({"milvus": None, "etcd": None, "minio": None})
                depends_on.update({"milvus": {"condition": "service_healthy"}})

            echo.info(f"A default {config.vectordb_type.capitalize()} setup is created.")

    if not config.custom_mongo_db_server:
        services.update(deepcopy(DOCKER_COMPOSE_MONGO_DB))
        volumes["mongo"] = None
        depends_on.update({"mongo": {"condition": "service_healthy"}})

    environment = cast("list", compose_server["server"]["environment"])
    for api_endpoint_key in config.infra_env:
        environment.append(api_endpoint_key + "=${" + api_endpoint_key + "}")

    if config.otel.docker_compose:
        services.update(deepcopy(config.otel.docker_compose))
        depends_on["otel-collector"] = {"condition": "service_started"}

    if config.falkordb.docker_compose:
        services.update(deepcopy(config.falkordb.docker_compose))
        volumes["falkordb_data"] = None
        depends_on["falkordb"] = {"condition": "service_healthy"}

    if config.falkordb.envs.get("DF_GRAPH__ENABLED") == "true":
        server_docker_envs.extend(DOCKER_COMPOSE_SERVER_FALKORDB_ENVS)

    if config.otel.envs.get("DF_OTEL_TRACING_ENABLED") == "true" and config.otel.envs.get(
        "DF_OTEL_EXPORTER_OTLP_ENDPOINT"
    ):
        environment.append("DF_OTEL_EXPORTER_OTLP_ENDPOINT=${DF_OTEL_EXPORTER_OTLP_ENDPOINT}")
        environment.append("DF_OTEL_TRACING_ENABLED=${DF_OTEL_TRACING_ENABLED}")

    if not config.is_vectordb_active:
        compose_server["server"]["environment"] = [
            env for env in environment if not env.startswith("DF_VECTOR_DATABASE__") or "ACTIVE" in env
        ]

    if depends_on:
        compose_server["server"]["depends_on"] = depends_on

    if config.local_image:
        compose_server["server"]["pull_policy"] = "never"

    services.update(compose_server)

    for _, service in services.items():
        add_network_to_service(service, config.docker_network)

    # Create directories for plugins and storage so Docker never has to auto-create these
    # bind-mount sources itself (which it would do as root, breaking later writes as this user).
    plugins_directory = config.directory / "plugins"
    try:
        plugins_directory.mkdir(exist_ok=True)
    except OSError as exc:
        echo.error(f"Unable to create {plugins_directory}: {exc}.")
        reraise_if_debug(exc)
    try:
        DF_SERVER_STORAGE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        echo.error(f"Unable to create {DF_SERVER_STORAGE_DIRECTORY}: {exc}.")
        reraise_if_debug(exc)

    services["server"]["volumes"] = [
        f"{DF_SERVER_STORAGE_DIRECTORY}:/app/storage",
        f"{plugins_directory.as_posix()}:/app/plugins",
    ]

    if config.dev:
        expose_ports_to_host(services)
        echo.warning("Dev mode: internal service ports are exposed to the host. Do not use in production.")

    save_compose_file(
        {"services": services, "volumes": volumes, "networks": {config.docker_network: {"external": True}}},
        config.directory / DOCKER_COMPOSE_CONFIG_FILENAME,
    )
    try:
        run(["docker", "compose", "pull"], config.directory, raises=DockerError)
    except DockerError as exc:
        echo.error(f"Failed to pull docker image(s): {exc}\nCheck registry access, credentials, and disk space.")
        reraise_if_debug(exc)
    start_hint = (
        "Starting it now to run the template's post-start actions."
        if will_auto_start
        else "To start the docker image - `deepfellow server start`."
    )
    echo.success(f"DeepFellow Server Installed.\n{start_hint}\nFor info about installation - `deepfellow server info`.")


@translate_to_install_error
def install(
    directory: Path = DF_SERVER_DIRECTORY,
    port: int = DF_SERVER_PORT,
    image: str = DF_SERVER_IMAGE,
    local_image: bool = False,
    otel_url: str | None = None,
    otel_local: bool = False,
    infra_url: str = DF_INFRA_URL,
    infra_api_key: str | None = None,
    docker_network: str = DF_INFRA_DOCKER_NETWORK,
    mongodb_url: str = DF_MONGO_URL,
    mongodb_port: int = DF_MONGO_PORT,
    mongodb_database_name: str = DF_MONGO_DB,
    mongodb_username: str = "",
    mongodb_password: str = "",
    vectordb_active: bool = bool(DEFAULT_VECTOR_DATABASE["provider"]["active"]),
    vectordb_type: VectorDBTypeChoice = VectorDBTypeChoice(DEFAULT_VECTOR_DATABASE_TYPE),
    vectordb_url: str = DEFAULT_VECTOR_DATABASE["provider"]["url"],
    vectordb_database_name: str = MILVUS_DATABASE["provider"]["db"],
    vectordb_username: str = "",
    vectordb_password: str = "",
    embedding_model: str = DEFAULT_VECTOR_DATABASE["embedding"]["model"],
    embedding_size: str = DEFAULT_VECTOR_DATABASE["embedding"]["size"],
    embedding_sparse: bool = False,
    falkordb_active: bool = False,
    falkordb_url: str = DF_FALKORDB_URL,
    falkordb_username: str = "",
    falkordb_password: str = "",
    force_install: bool = False,
    dev: bool = False,
    template: str | None = None,
    admin_name: str | None = None,
    admin_email: str | None = None,
    admin_password: str | None = None,
    explicitly_provided: Collection[str] = frozenset(),
) -> None:
    """Install DeepFellow Server with docker."""
    if otel_local and otel_url:
        echo.error("--otel-local and --otel-url are mutually exclusive; pass only one.")
        raise typer.Exit(1)

    echo.info("Installing DeepFellow Server.")

    context = inspect(
        directory=directory,
        image=image,
        local_image=local_image,
        force_install=force_install,
        template=template,
        admin_name=admin_name,
        admin_email=admin_email,
        admin_password=admin_password,
    )

    config = resolve(
        context,
        port=port,
        image=image,
        otel_url=otel_url,
        otel_local=otel_local,
        infra_url=infra_url,
        infra_api_key=infra_api_key,
        docker_network=docker_network,
        mongodb_url=mongodb_url,
        mongodb_port=mongodb_port,
        mongodb_database_name=mongodb_database_name,
        mongodb_username=mongodb_username,
        mongodb_password=mongodb_password,
        vectordb_active=vectordb_active,
        vectordb_type=vectordb_type,
        vectordb_url=vectordb_url,
        vectordb_database_name=vectordb_database_name,
        vectordb_username=vectordb_username,
        vectordb_password=vectordb_password,
        embedding_model=embedding_model,
        embedding_size=embedding_size,
        embedding_sparse=embedding_sparse,
        falkordb_active=falkordb_active,
        falkordb_url=falkordb_url,
        falkordb_username=falkordb_username,
        falkordb_password=falkordb_password,
        local_image=local_image,
        dev=dev,
        explicitly_provided=explicitly_provided,
    )

    post_start_actions = context.resolved_template["post_start_actions"] if context.resolved_template else []
    apply(config, will_auto_start=bool(post_start_actions))

    if post_start_actions:
        try:
            start_server(config.directory)
        except (DockerNetworkError, typer.Exit) as exc:
            reason = str(exc) if isinstance(exc, DockerNetworkError) else "see console output above for details."
            echo.error(f"Failed to start server for template post start actions: {reason}")
            reraise_if_debug(exc)

        # A server.create_admin action's "directory" kwarg must target the directory actually
        # installed to, not whatever a template guessed (the built-in "workspace" template bakes
        # it to the default DF_SERVER_DIRECTORY, which is wrong whenever --directory overrides
        # it). Scoped to server.create_admin, like _coerce_directory() and
        # _validate_non_interactive_post_start_actions(), so a future action type without a
        # "directory" kwarg isn't silently handed one it never asked for.
        total = len(post_start_actions)
        for index, action in enumerate(post_start_actions, start=1):
            if action["function"] == "server.create_admin":
                template_directory = action["kwargs"].get("directory")
                if template_directory is not None and template_directory != config.directory:
                    echo.warning(
                        f"Post-start action {index}/{total} ('{action['function']}') set its own "
                        f"'directory' ({template_directory}); overriding it with the actually-installed "
                        f"server's directory ({config.directory})."
                    )
                action["kwargs"]["directory"] = config.directory
                action["kwargs"].update(resolve_admin_kwargs(action["kwargs"], admin_name, admin_email, admin_password))
            try:
                dispatch_post_start_action(action)
            except InstallError as exc:
                echo.error(
                    f"Post-start action {index}/{total} ('{action['function']}') failed: {exc}\n"
                    f"Server is already installed and running; {index - 1} of {total} action(s) "
                    "completed before this failure."
                )
                reraise_if_debug(exc)
            except Exception as exc:
                # dispatch_post_start_action only translates typer.Exit/BadParameter/Docker/OSError
                # failures into InstallError (see deepfellow.common.templates.dispatch_post_start_action);
                # any other exception type propagates unmodified. Catch it here too, so a future
                # post-start action that raises outside that translated set still gets the same
                # operator-facing message instead of a bare traceback.
                echo.error(
                    f"Post-start action {index}/{total} ('{action['function']}') failed unexpectedly: {exc}\n"
                    f"Server is already installed and running; {index - 1} of {total} action(s) "
                    "completed before this failure."
                )
                reraise_if_debug(exc)
