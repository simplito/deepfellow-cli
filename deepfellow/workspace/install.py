# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Install workspace typer command."""

from collections.abc import Callable
from pathlib import Path

import typer

from deepfellow.common.defaults import (
    DF_INFRA_DOCKER_NETWORK,
    DF_WORKSPACE_IMAGE,
    DF_WORKSPACE_PORT,
    DF_WORKSPACE_SMALL_MODEL,
)
from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.exceptions import InstallError, reraise_if_debug
from deepfellow.common.install import assert_docker
from deepfellow.common.validation import (
    validate_bind_address,
    validate_email,
    validate_mongo_url,
    validate_origin,
    validate_origins,
    validate_password,
    validate_redis_url,
    validate_url,
)
from deepfellow.workspace.utils.configure import SMTP_KEYS, prompt_optional_settings
from deepfellow.workspace.utils.install import (
    REQUIRED_VALUES,
    confirm_overwrite,
    read_existing_env,
    resolve_stack_settings,
)
from deepfellow.workspace.utils.install import install as install_util
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.public_url import apply_https_settings, insecure_context_warning, resolve_public_url
from deepfellow.workspace.utils.server import list_server_models, resolve_server_ids, server_lookup_failed
from deepfellow.workspace.utils.validation import validate_mcp_auth_token

app = typer.Typer()

_SERVER_ID_KEYS = ("DF_SERVER_ORGANIZATION_ID", "DF_SERVER_PROJECT_ID")
_SMALL_MODEL_CHOICE_LIMIT = 10
_SMALL_MODEL_EXPLANATION = (
    "Workspace uses a small, fast model for background tasks: session titles, suggestions, skill drafts, "
    "questionnaires, summarizing long conversations to fit the context window, and verifying answers against "
    "the knowledge base. It must be a model your DeepFellow Server project can use."
)


def _not_empty(value: str) -> str:
    """Validate that a prompted value is not blank."""
    if not value.strip():
        raise typer.BadParameter("A value is required.")
    return value.strip()


def _reset_keys(local_mongodb: bool, local_redis: bool, no_smtp: bool) -> tuple[str, ...]:
    """List the .env keys of a previous installation that the reset flags ask to forget.

    Args:
        local_mongodb: Go back to the Mongo installed with Workspace.
        local_redis: Go back to the Redis installed with Workspace.
        no_smtp: Forget the SMTP and sender settings.

    Returns:
        The keys to drop.
    """
    keys: list[str] = []
    if local_mongodb:
        keys += ["MONGO_DB_URL", "MONGO_DB_NAME"]
    if local_redis:
        keys.append("REDIS_URL")
    if no_smtp:
        keys += SMTP_KEYS
    return tuple(dict.fromkeys(keys))


def _note_mcp_auth_token(env: dict[str, str], directory: Path) -> None:
    """Tell where the bearer token protecting the /mcp endpoint is kept.

    Args:
        env: The .env content that was written.
        directory: Install directory.
    """
    if env.get("MCP_AUTH_TOKEN"):
        echo.info(
            f"The /mcp endpoint requires the bearer token MCP_AUTH_TOKEN from {directory / '.env'} "
            "(readable by you only); give it to MCP clients."
        )


def _note_admin_password(env: dict[str, str], directory: Path) -> None:
    """Tell where the initial admin password was left, since it stays in .env after the first start.

    Args:
        env: The .env content that was written.
        directory: Install directory.
    """
    if env.get("BOOTSTRAP_ADMIN_PASSWORD"):
        echo.info(
            f"The initial admin password stays in {directory / '.env'} (readable by you only); "
            "once you have logged in, remove all three BOOTSTRAP_ADMIN_* lines from it (the app needs them together)."
        )


def _check_reset_flags(passed: dict[str, str | None], local_mongodb: bool, local_redis: bool, no_smtp: bool) -> None:
    """Refuse a reset flag combined with a value that sets the same thing.

    Args:
        passed: Values given explicitly, keyed by .env name.
        local_mongodb: Go back to the Mongo installed with Workspace.
        local_redis: Go back to the Redis installed with Workspace.
        no_smtp: Forget the SMTP and sender settings.

    Raises:
        InstallError: When a reset flag contradicts a given value.
    """
    if (local_mongodb and (passed["MONGO_DB_URL"] or passed["MONGO_DB_NAME"])) or (local_redis and passed["REDIS_URL"]):
        raise InstallError("--local-mongodb and --local-redis cannot be combined with the matching external URL.")
    if no_smtp and any(passed[key] for key in SMTP_KEYS):
        raise InstallError("--no-smtp cannot be combined with SMTP settings.")


def _fill_server_ids(passed: dict[str, str | None], key: str, existing: dict[str, str]) -> bool:
    """Take the organization and project ids from DeepFellow Server, which knows them from the API key.

    Ids given explicitly are never replaced, and ones kept from a previous installation are replaced, because
    the API key may now belong to another project.

    Args:
        passed: Values collected so far; the ids are written into it when Server reports them.
        key: The value being collected. Server is asked once, when this is the first id, and only if an id is missing.
        existing: Values of the previous installation; the URL and API key kept from it are used when not passed.

    Returns:
        Whether the ids were filled in, so the caller need not ask for them.
    """
    if key != _SERVER_ID_KEYS[0] or all(passed[id_key] for id_key in _SERVER_ID_KEYS):
        return False
    server_url = passed["DF_SERVER_URL"] or existing.get("DF_SERVER_URL")
    api_key = passed["DF_SERVER_API_KEY"] or existing.get("DF_SERVER_API_KEY")
    if not server_url or not api_key:
        return False
    ids = resolve_server_ids(server_url, api_key)
    if ids is None:
        if server_lookup_failed(server_url, api_key):
            echo.info(
                "Give the organization and project ids with --df-server-organization-id and --df-server-project-id."
            )
            return False
        echo.warning(
            "Could not get the organization and project ids from DeepFellow Server (GET /info with the given API key). "
            "The Server may be unreachable from this host (the URL for the container, e.g. http://server:8000/v1, "
            "may not resolve here), reject the key, or be too old to report them. "
            "Give them with --df-server-organization-id and --df-server-project-id."
        )
        return False
    for id_key, value in zip(_SERVER_ID_KEYS, ids, strict=True):
        passed[id_key] = passed[id_key] or value
    echo.info("Organization and project ids taken from DeepFellow Server.")
    return True


def _known_server_models(passed: dict[str, str | None], kept: str | None, existing: dict[str, str]) -> list[str] | None:
    """Ask DeepFellow Server which models it offers, when that is worth knowing.

    The lookup is skipped when there is no URL or API key to ask with, and when a small model kept from a previous
    installation is still paired with the URL and API key it was chosen for.

    Args:
        passed: Values collected so far.
        kept: The small model kept from a previous installation.
        existing: Values of the previous installation; the URL and API key kept from it are used when not passed.

    Returns:
        The model ids, or `None` when they are not known (no lookup, or Server did not answer).
    """
    server_url = passed["DF_SERVER_URL"] or existing.get("DF_SERVER_URL")
    api_key = passed["DF_SERVER_API_KEY"] or existing.get("DF_SERVER_API_KEY")
    if not server_url or not api_key:
        return None
    # A new API key may belong to another project, so the kept model may no longer be usable.
    server_changed = server_url != existing.get("DF_SERVER_URL") or api_key != existing.get("DF_SERVER_API_KEY")
    if kept and not server_changed:
        return None
    models = list_server_models(server_url, api_key)
    if models is not None and not models:
        echo.warning("DeepFellow Server reports no models for this API key's project.")
    return models


def _validate_small_model(models: list[str] | None) -> Callable[[str], str]:
    """Build a validator for the small model prompt.

    Args:
        models: Models DeepFellow Server offers, or `None` when they are not known and any non-empty name is accepted.

    Returns:
        The validation callback.
    """

    def validate(value: str) -> str:
        value = _not_empty(value)
        if models and value not in models:
            raise typer.BadParameter(f"Not available on DeepFellow Server. Available: {', '.join(models)}")
        return value

    return validate


def _collect_small_model(passed: dict[str, str | None], label: str, kept: str | None, existing: dict[str, str]) -> None:
    """Choose the small model, checking it against the models DeepFellow Server offers when they are known.

    When Server does not answer, the default model is suggested without a check. When it answers and the default
    model is not among its models, the default is not suggested: a list or an unprefilled prompt is shown, and
    non-interactive mode fails. A model kept from a previous installation is dropped when Server does not offer it.

    Args:
        passed: Values collected so far; the model is written into it when chosen here.
        label: Prompt label of the value.
        kept: The value kept from a previous installation.
        existing: Values of the previous installation; the URL and API key kept from it are used when not passed.

    Raises:
        InstallError: In non-interactive mode, when Server's models do not include any usable default.
    """
    models = _known_server_models(passed, kept, existing)
    if kept and models is not None and kept not in models:
        echo.warning(
            f"The small model {kept} kept from the existing installation is not available on DeepFellow Server."
        )
        kept = None
    if models and len(models) == 1 and not kept:
        passed["SMALL_MODEL"] = models[0]
        echo.info(f"Only one model is available on DeepFellow Server, using it as the small model: {models[0]}")
        return
    default = kept or (DF_WORKSPACE_SMALL_MODEL if models is None or DF_WORKSPACE_SMALL_MODEL in models else None)
    if default is None and not is_interactive():
        available = (
            "none"
            if not models
            else ", ".join(models)
            if len(models) <= _SMALL_MODEL_CHOICE_LIMIT
            else f"{len(models)} models"
        )
        raise InstallError(
            f"The default small model {DF_WORKSPACE_SMALL_MODEL} is not available on DeepFellow Server "
            f"(available: {available}). Pass --small-model to use another one."
        )
    if not is_interactive():
        if kept:
            echo.info(f"{label}: {kept} (kept from the existing installation)")
        else:
            passed["SMALL_MODEL"] = default
            echo.info(f"{label}: {default} (default)")
        return
    echo.info(_SMALL_MODEL_EXPLANATION)
    if default is None:
        echo.info(f"The default {DF_WORKSPACE_SMALL_MODEL} is not available on DeepFellow Server.")
        if models and len(models) <= _SMALL_MODEL_CHOICE_LIMIT:
            choice = echo.choice(label, models)
            if choice is None:
                raise typer.Exit(1)
            passed["SMALL_MODEL"] = choice
            return
    # The current value is the default, so Enter keeps it and anything else replaces it.
    passed["SMALL_MODEL"] = echo.prompt_until_valid(
        label, _validate_small_model(models), default=default, password=False
    )


def _flag(value: bool | None) -> str | None:
    """Render an optional boolean flag the way the app's .env expects it."""
    return None if value is None else str(value).lower()


def _collect_required_values(passed: dict[str, str | None], existing: dict[str, str]) -> None:
    """Fill the required settings missing from `passed` (from the server, a prompt, or the existing install).

    Args:
        passed: Values given on the command line; updated in place.
        existing: Values kept from a previous installation.
    """
    for key, label in REQUIRED_VALUES.items():
        kept = existing.get(key)
        if _fill_server_ids(passed, key, existing) or passed[key]:
            continue
        if key == "SMALL_MODEL":
            _collect_small_model(passed, label, kept, existing)
            continue
        if is_interactive():
            # The current value is the default, so Enter keeps it and anything else replaces it.
            validation = validate_url if key == "DF_SERVER_URL" else _not_empty
            passed[key] = echo.prompt_until_valid(label, validation, default=kept, password=key == "DF_SERVER_API_KEY")
        elif kept:
            shown = "(hidden)" if key == "DF_SERVER_API_KEY" else kept
            echo.info(f"{label}: {shown} (kept from the existing installation)")


def _resolve_address(passed: dict[str, str | None], existing: dict[str, str], port: int) -> None:
    """Choose the Workspace address, warn when the browser will block features on it, and set up https.

    Args:
        passed: Values collected so far; updated in place.
        existing: Values kept from a previous installation.
        port: Published Workspace port, for the default address.
    """
    public_url = resolve_public_url(passed, existing, port)
    if warning := insecure_context_warning(public_url):
        echo.warning(warning)
    apply_https_settings(passed, existing, public_url)


@app.command()
def install(
    directory: Path = directory_option(),
    image: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_IMAGE",
        help=f"DeepFellow Workspace image. Default: {DF_WORKSPACE_IMAGE}; a reinstall keeps the previous value "
        "unless this is given.",
    ),
    port: int | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_PORT",
        min=1,
        max=65535,
        help=f"Port to serve Workspace from. Default: {DF_WORKSPACE_PORT}; a reinstall keeps the previous value "
        "unless this is given.",
    ),
    bind_address: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_BIND_ADDRESS",
        callback=validate_bind_address,
        help="Host address to publish the Workspace port on, e.g. 127.0.0.1. Default: all interfaces; a reinstall "
        "keeps the previous value unless this is given.",
    ),
    docker_network: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_DOCKER_NETWORK",
        help="The Docker network name for communication with DeepFellow Server. "
        f"Default: {DF_INFRA_DOCKER_NETWORK}; a reinstall keeps the previous value unless this is given.",
    ),
    public_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_PUBLIC_URL",
        callback=validate_origin,
        help="Origin browsers reach Workspace at; asked for when not given (unless --yes or --non-interactive). "
        "Default: http://localhost:<port>; a reinstall keeps the previous value unless this is given. Over http, "
        "use localhost: on other hosts browsers block e.g. copying and attachments. An https origin assumes a "
        "TLS-terminating reverse proxy and enables --trusted-proxy (see there).",
    ),
    df_server_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_DF_SERVER_URL",
        callback=validate_url,
        help="DeepFellow Server URL, including /v1, as the Workspace container reaches it (e.g. "
        "http://server:8000/v1 on the infra network; localhost does not work from inside the container). "
        "The CLI uses it too, so when it is not reachable from this host the ids and model are asked for.",
    ),
    df_server_api_key: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_DF_SERVER_API_KEY", help="DeepFellow Server project API key."
    ),
    df_server_organization_id: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_DF_SERVER_ORGANIZATION_ID",
        help="DeepFellow Server organization id. Default: taken from DeepFellow Server by the API key.",
    ),
    df_server_project_id: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_DF_SERVER_PROJECT_ID",
        help="DeepFellow Server project id. Default: taken from DeepFellow Server by the API key.",
    ),
    small_model: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_SMALL_MODEL",
        help="Small model served by DeepFellow Server, used for background tasks (session titles, suggestions, "
        f"summarizing long conversations, ...). Default: the only model on DeepFellow Server, else "
        f"{DF_WORKSPACE_SMALL_MODEL}; a reinstall keeps the previous value unless this is given.",
    ),
    admin_name: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_NAME", help="Name of the initial admin account."
    ),
    admin_email: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_EMAIL",
        callback=validate_email,
        help="E-mail of the initial admin account.",
    ),
    admin_password: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_BOOTSTRAP_ADMIN_PASSWORD",
        callback=validate_password,
        help="Password of the initial admin account.",
    ),
    smtp_host: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_HOST", help="SMTP server host, to send e-mails."
    ),
    smtp_port: int | None = typer.Option(
        None, envvar="DF_WORKSPACE_SMTP_PORT", min=1, max=65535, help="SMTP server port. Default: 587."
    ),
    smtp_secure: bool | None = typer.Option(
        None,
        "--smtp-secure/--no-smtp-secure",
        envvar="DF_WORKSPACE_SMTP_SECURE",
        help="Use TLS from the start of the connection (usually with port 465). Default: no.",
    ),
    smtp_username: str | None = typer.Option(None, envvar="DF_WORKSPACE_SMTP_USERNAME", help="SMTP username."),
    smtp_password: str | None = typer.Option(None, envvar="DF_WORKSPACE_SMTP_PASSWORD", help="SMTP password."),
    email_from_address: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_EMAIL_FROM_ADDRESS", callback=validate_email, help="Sender e-mail address."
    ),
    email_from_name: str | None = typer.Option(None, envvar="DF_WORKSPACE_EMAIL_FROM_NAME", help="Sender name."),
    mongodb_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MONGO_DB_URL",
        callback=validate_mongo_url,
        help="Use this external MongoDB (a replica set) instead of installing one.",
    ),
    mongodb_database_name: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MONGO_DB_NAME",
        help="Database name in the external MongoDB; overrides the one in --mongodb-url.",
    ),
    redis_url: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_REDIS_URL",
        callback=validate_redis_url,
        help="Use this external Redis instead of installing one.",
    ),
    trusted_proxy: bool | None = typer.Option(
        None,
        "--trusted-proxy/--no-trusted-proxy",
        envvar="DF_WORKSPACE_TRUSTED_PROXY_ENABLED",
        help="Trust X-Forwarded-For / X-Real-IP; enable only behind a reverse proxy that sets them. "
        "Default: on for an https --public-url, unless a previous install was run with --no-trusted-proxy.",
    ),
    trusted_origins: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_TRUSTED_ORIGINS",
        callback=validate_origins,
        help="Other origins Workspace trusts besides --public-url, comma-separated (e.g. more addresses of the "
        "reverse proxy). Asked for with an https --public-url (unless --yes or --non-interactive); a reinstall "
        "keeps the previous value unless this is given.",
    ),
    mcp_auth_token: str | None = typer.Option(
        None,
        envvar="DF_WORKSPACE_MCP_AUTH_TOKEN",
        callback=validate_mcp_auth_token,
        help="Require this bearer token (min 16 characters) on the /mcp endpoint.",
    ),
    local_mongodb: bool = typer.Option(
        False,
        "--local-mongodb",
        help="On a reinstall, go back to the Mongo installed with Workspace instead of an external one.",
    ),
    local_redis: bool = typer.Option(
        False,
        "--local-redis",
        help="On a reinstall, go back to the Redis installed with Workspace instead of an external one.",
    ),
    no_smtp: bool = typer.Option(False, "--no-smtp", help="On a reinstall, forget the SMTP and sender settings."),
    force_install: bool = typer.Option(
        False, help="Skip the question about overwriting an existing directory (e.g. one kept by uninstall)."
    ),
) -> None:
    """Install DeepFellow Workspace with docker (own Mongo and Redis included by default)."""
    passed: dict[str, str | None] = {
        "DF_SERVER_URL": df_server_url,
        "DF_SERVER_API_KEY": df_server_api_key,
        "DF_SERVER_ORGANIZATION_ID": df_server_organization_id,
        "DF_SERVER_PROJECT_ID": df_server_project_id,
        "SMALL_MODEL": small_model,
        "PUBLIC_URL": public_url,
        "BOOTSTRAP_ADMIN_NAME": admin_name,
        "BOOTSTRAP_ADMIN_EMAIL": admin_email,
        "BOOTSTRAP_ADMIN_PASSWORD": admin_password,
        "SMTP_HOST": smtp_host,
        "SMTP_PORT": None if smtp_port is None else str(smtp_port),
        "SMTP_SECURE": _flag(smtp_secure),
        "SMTP_USERNAME": smtp_username,
        "SMTP_PASSWORD": smtp_password,
        "EMAIL_FROM_ADDRESS": email_from_address,
        "EMAIL_FROM_NAME": email_from_name,
        "MONGO_DB_URL": mongodb_url,
        "MONGO_DB_NAME": mongodb_database_name,
        "REDIS_URL": redis_url,
        "TRUSTED_PROXY_ENABLED": _flag(trusted_proxy),
        "TRUSTED_ORIGINS": trusted_origins,
        "MCP_AUTH_TOKEN": mcp_auth_token,
    }
    reset = _reset_keys(local_mongodb, local_redis, no_smtp)
    try:
        _check_reset_flags(passed, local_mongodb, local_redis, no_smtp)
        assert_docker()
        existing = read_existing_env(directory)
        image, port, bind_address, docker_network = resolve_stack_settings(
            existing, image, port, bind_address, docker_network
        )
        overwrite = None
        if directory.is_dir() and not force_install:
            # Ask before the value prompts, so a refusal does not waste the answers.
            overwrite = confirm_overwrite(directory)
            if not overwrite:
                raise typer.Exit(1)
        _collect_required_values(passed, existing)
        _resolve_address(passed, existing, port)
        prompt_optional_settings(passed, existing)
        env = install_util(
            directory=directory,
            image=image,
            port=port,
            bind_address=bind_address,
            docker_network=docker_network,
            existing=existing,
            passed=passed,
            force_install=force_install,
            overwrite=overwrite,
            reset=reset,
        )
    except (InstallError, OSError, ValueError) as exc:
        echo.error(str(exc))
        reraise_if_debug(exc)
    echo.success(f"DeepFellow Workspace installed. Open it at {env['PUBLIC_URL']}.")
    _note_mcp_auth_token(env, directory)
    _note_admin_password(env, directory)
