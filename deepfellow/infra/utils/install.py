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
from copy import deepcopy
from dataclasses import dataclass
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
from deepfellow.common.templates import InstallTemplate
from deepfellow.common.validation import validate_df_name, validate_url
from deepfellow.infra.utils.docker import start_infra
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
) -> InstallContext:
    """Resolve --template, then do a Docker check, directory creation, and existing .env read-back.

    Resolves and validates `template` (via resolve_template()), if given, before touching Docker or
    the filesystem, so a bad template fails fast without side effects. No prompts, no network/compose
    writes.

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
        directory, error_message="Unable to create DeepFellow Infra directory.", force_install=force_install
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


# (template config key, CLI option's own original default, matching key in a prior install's .env)
_MERGEABLE_FIELDS: tuple[tuple[str, Any, str], ...] = (
    ("port", DF_INFRA_PORT, "df_infra_port"),
    ("infra_name", DF_INFRA_NAME, "df_name"),
    ("infra_url", DF_INFRA_URL, "df_infra_url"),
    ("docker_network", DF_INFRA_DOCKER_NETWORK, "df_infra_docker_subnet"),
)


def _merge_template_config(
    template_config: dict[str, Any],
    original_env_content: EnvDict,
    values: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    """Fill in CLI-level install values from a template's config, without overriding what should win.

    Precedence, highest to lowest: an explicit CLI flag (the arg no longer equals its own original
    default) always wins; a value already configured by a prior install (found in that install's
    `.env`, merged with any `config.json` values by `merge_config_json_into_env()` before
    `original_env_content` reaches here) is preserved next - a template must not silently discard
    existing configuration; only then does the template's config value apply; the CLI option's
    hardcoded default is the fallback.

    Args:
        template_config: The resolved template's "config" mapping (empty if no template was given).
        original_env_content: The prior install's .env content, merged with config.json (empty if
            neither existed).
        values: CLI-resolved values for the fields in `_MERGEABLE_FIELDS`, keyed by their template
            config key, e.g. {"port": port, "infra_name": infra_name, ...}.

    Returns:
        The merged values (same keys as `values`), plus the subset of its keys that came from the
        template. `resolve()` passes force_provided=True for infra_name/infra_url/docker_network's
        prompt when the key is in this set, so it isn't re-asked; `port` has no prompt of its own,
        so its merged value (already restored to a prior value when one blocked the template, see
        above) is used as-is.

    Raises:
        InstallError: If a prior install's .env has a non-numeric port value.
    """
    merged = dict(values)
    from_template: set[str] = set()

    for key, own_default, env_key in _MERGEABLE_FIELDS:
        if key not in template_config:
            continue
        if merged[key] != own_default:
            continue  # an explicit CLI flag already wins

        prior_value = original_env_content.get(env_key)
        if prior_value:
            # infra_name/infra_url/docker_network restore the prior value via their own prompt's
            # `default=` in resolve(); port has no prompt of its own, so it must be restored here
            # or the CLI's hardcoded default would silently overwrite it when .env is saved.
            if key == "port":
                try:
                    merged[key] = int(str(prior_value))
                except ValueError:
                    raise InstallError(
                        f"Existing .env has an invalid {env_key.upper()} value ({prior_value!r}); "
                        "fix or remove it before retrying."
                    ) from None
            continue  # a prior install's value must not be silently discarded

        merged[key] = template_config[key]
        from_template.add(key)

    return merged, from_template


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
) -> InstallConfig:
    """Prompt the user for / apply CLI overrides to the remaining install values.

    Before prompting, merges `context.resolved_template`'s config into port/infra_name/infra_url/
    docker_network via `_merge_template_config()`: an explicit CLI flag always wins, a value already
    configured by a prior install (found in `context.original_env_content`) is preserved next, and
    only then does the template's config value apply. See `_merge_template_config()`.

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

    Returns:
        InstallConfig: The fully-resolved installation configuration.
    """
    original_env_content = context.original_env_content

    template_config = context.resolved_template["config"] if context.resolved_template else {}
    merged, from_template = _merge_template_config(
        template_config,
        original_env_content,
        {"port": port, "infra_name": infra_name, "infra_url": infra_url, "docker_network": docker_network},
    )
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
        force_provided="infra_name" in from_template,
    )

    df_infra_url = echo.prompt_until_valid(
        "Provide a DF_INFRA_URL for this Infra",
        validate_url,
        error_message="Invalid DF_INFRA_URL. Please try again.",
        from_args=infra_url,
        original_default=DF_INFRA_URL,
        default=original_env_content.get("df_infra_url", infra_url),
        force_provided="infra_url" in from_template,
    )

    # Find out which docker network to use
    docker_network = echo.prompt(
        "Provide a docker network name",
        from_args=docker_network,
        original_default=DF_INFRA_DOCKER_NETWORK,
        default=original_env_content.get("df_infra_docker_subnet", docker_network),
        force_provided="docker_network" in from_template,
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
        infra_localhost_url = f"http://localhost:{config.infra_port}"
        total = len(post_start_actions)
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
                dispatch_post_start_action(action)
            except InstallError as exc:
                # dispatch_post_start_action is decorated with @translate_to_install_error, which
                # unconditionally converts any typer.Exit it raises into InstallError - so
                # InstallError is the only failure mode reachable here, ever.
                echo.error(
                    f"Post-start action {index}/{total} ('{action['function']}') failed: {exc}\n"
                    f"Infra is already installed and running; {index - 1} of {total} action(s) "
                    "completed before this failure."
                )
                raise typer.Exit(1) from exc
