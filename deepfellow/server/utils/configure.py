# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Configure methods."""

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.config import dict_to_env
from deepfellow.common.defaults import (
    ALLOWED_VECTOR_DB_TYPES,
    DEFAULT_OTEL_URL,
    DEFAULT_VECTOR_DATABASE,
    DEFAULT_VECTOR_DATABASE_TYPE,
    DF_FALKORDB_PORT,
    DF_FALKORDB_URL,
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_PORT,
    DF_MONGO_URL,
    DOCKER_COMPOSE_FALKORDB,
    DOCKER_COMPOSE_OTEL_COLLECTOR,
    MILVUS_DATABASE,
    MONGO_DB_INIT_SH,
    OTEL_COLLECTOR_CONFIG,
    OTEL_COLLECTOR_CONFIG_DEBUG_ONLY,
    QDRANT_DATABASE,
    SPARSE_EMBEDDING_MODEL,
    SPARSE_EMBEDDING_SIZE,
    VECTOR_DATABASES,
)
from deepfellow.common.docker import (
    DockerError,
    load_compose_file,
    remove_volume,
    resolve_compose_volume_name,
    save_compose_file,
    volume_exists,
)
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.generate import generate_password
from deepfellow.common.state import state
from deepfellow.common.validation import validate_connection_string, validate_truthy, validate_url, validate_username


def should_use_vector_db(
    vectordb_active: int,
) -> bool:
    """Check if server should configure vector database."""
    # If from the CLI args we've got disable vector DB and this choice is not the default one,
    # we just display the warning and set the vector DB as inactive.
    default_vectordb_active = DEFAULT_VECTOR_DATABASE["provider"]["active"]
    if not vectordb_active and vectordb_active != default_vectordb_active:
        echo.warning("You've chosen to not use vector database.")
        return False

    # If we are in interactive mode, user will answer the question if the vector DB is wanted.
    # In non-interactive mode the default answer will be taken (default_vectordb_active)
    if not echo.confirm("Do you want to use a vector database with DeepFellow?", default=bool(default_vectordb_active)):
        echo.warning("You've chosen to not use vector database.")
        return False

    return True


def is_custom_vectordb(
    vectordb_type: str,
    vectordb_url: str,
    vectordb_database_name: str,
) -> bool:
    """Check if user wants to connect an existing vector database instead of a local one.

    By default DeepFellow installs a local vector database. The user has to explicitly
    opt in to connecting an existing/external instance.
    """
    any_milvus_arg_provided = (
        vectordb_url != MILVUS_DATABASE["provider"]["url"]
        or vectordb_database_name != MILVUS_DATABASE["provider"]["db"]
    )

    if (vectordb_type == "qdrant" and (vectordb_url != QDRANT_DATABASE["provider"]["url"])) or (
        vectordb_type == "milvus" and any_milvus_arg_provided
    ):
        return True

    return not echo.confirm("Install a local vector database for DeepFellow Server?", default=True)


def configure_milvus_specific_fields(
    original_provider: dict[str, str],
    vectordb_database_name: str,
    vectordb_username: str | None,
    vectordb_password: str | None,
    *,
    force_provided_database_name: bool = False,
) -> dict[str, str]:
    """Configure fields specific for milvus.

    An explicitly-provided ``vectordb_username``/``vectordb_password`` must win over a stale
    value already present in ``original_provider`` (loaded from an existing ``.env`` on
    reconfigure). ``echo.prompt_until_valid`` detects "explicitly provided on the CLI" by
    comparing ``from_args`` against ``original_default``, so ``from_args`` must stay the raw,
    unmutated CLI value - generating a fallback into the same variable before this comparison
    (as a previous version did) makes it always differ from ``original_default`` and defeats
    the detection, so the ``.env`` value would never be used even when nothing was passed on
    the CLI.

    Args:
        original_provider: The prior install's vector DB provider settings, if any.
        vectordb_database_name: Requested Milvus database name.
        vectordb_username: Requested Milvus username.
        vectordb_password: Requested Milvus password.
        force_provided_database_name: Treat vectordb_database_name as explicitly provided even
            if it equals its own original_default - needed when it was merged in from a
            --template config value equal to that default. See
            deepfellow.common.echo.get_return_value. Username/password have no --template config
            key of their own, so they need no equivalent flag.
    """
    default_username = original_provider.get("user") or generate_password(8)
    default_password = original_provider.get("password") or generate_password(12)

    return {
        "db": echo.prompt_until_valid(
            "Provide Milvus provider database name",
            validate_truthy,
            from_args=vectordb_database_name,
            original_default=MILVUS_DATABASE["provider"]["db"],
            default=original_provider.get("db", vectordb_database_name),
            force_provided=force_provided_database_name,
        ),
        "user": echo.prompt_until_valid(
            "Provide Milvus provider user",
            validate_truthy,
            from_args=vectordb_username,
            original_default="",
            default=default_username,
        ),
        "password": echo.prompt_until_valid(
            "Provide Milvus provider password",
            validate_truthy,
            from_args=vectordb_password,
            original_default="",
            default=default_password,
            password=True,
        ),
    }


def _choose_embedding_type(
    original_env: dict[str, Any],
    embedding_model: str,
    embedding_sparse: bool,
) -> str:
    """Ask user to choose embedding type, or return 'sparse' when flag is set."""
    if embedding_sparse:
        return "sparse"
    original_embedding = original_env.get("df_vector_database", {}).get("embedding", {})
    existing_model = original_embedding.get("model", embedding_model)
    default_type = "sparse" if existing_model == SPARSE_EMBEDDING_MODEL else "dense"
    return echo.choice("Choose embedding type", choices=["dense", "sparse"], default=default_type)


def _build_embedding_config(
    embedding_type: str,
    infra_url: str,
    original_env: dict[str, Any],
    embedding_model: str,
    embedding_size: str,
    *,
    force_provided_model: bool = False,
    force_provided_size: bool = False,
) -> dict[str, str | int]:
    """Build embedding config dict, prompting for model/size when dense.

    Args:
        embedding_type: "dense" or "sparse", as chosen by _choose_embedding_type.
        infra_url: DeepFellow Infra URL, used as the embedding endpoint.
        original_env: The prior install's .env content, if any.
        embedding_model: Requested embedding model (dense only).
        embedding_size: Requested embedding size (dense only).
        force_provided_model: Treat embedding_model as explicitly provided even if it equals its
            own original_default - needed when it was merged in from a --template config value
            equal to that default. See deepfellow.common.echo.get_return_value.
        force_provided_size: Same as force_provided_model, for embedding_size.
    """
    if embedding_type == "sparse":
        echo.info(f"Using {SPARSE_EMBEDDING_MODEL} for sparse embeddings")
        return {
            "active": 1,
            "endpoint": infra_url,
            "model": SPARSE_EMBEDDING_MODEL,
            "size": SPARSE_EMBEDDING_SIZE,
        }
    original_embedding = original_env.get("df_vector_database", {}).get("embedding", {})
    existing_model = original_embedding.get("model", embedding_model)
    return {
        "active": 1,
        "endpoint": infra_url,
        "model": echo.prompt(
            "Provide the model for embedding",
            from_args=embedding_model,
            original_default=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
            default=existing_model,
            force_provided=force_provided_model,
        ),
        "size": echo.prompt(
            "Provide the embedding size",
            from_args=embedding_size,
            original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
            default=original_embedding.get("size", embedding_size),
            force_provided=force_provided_size,
        ),
    }


def configure_embedding(
    infra_url: str,
    original_env: dict[str, Any],
    embedding_model: str,
    embedding_size: str,
    embedding_sparse: bool = False,
    *,
    force_provided_model: bool = False,
    force_provided_size: bool = False,
) -> dict[str, str | int]:
    """Configure embedding fields."""
    embedding_type = _choose_embedding_type(original_env, embedding_model, embedding_sparse)
    return _build_embedding_config(
        embedding_type,
        infra_url,
        original_env,
        embedding_model,
        embedding_size,
        force_provided_model=force_provided_model,
        force_provided_size=force_provided_size,
    )


def configure_vector_db(
    infra_url: str,
    original_env_content: dict[str, Any],
    vectordb_active: int,
    vectordb_type: str,
    vectordb_url: str,
    vectordb_database_name: str,
    vectordb_username: str,
    vectordb_password: str,
    embedding_model: str,
    embedding_size: str,
    embedding_sparse: bool,
    default_vectordb_type: str,
    *,
    force_provided_type: bool = False,
    force_provided_url: bool = False,
    force_provided_database_name: bool = False,
    force_provided_model: bool = False,
    force_provided_size: bool = False,
) -> tuple[bool, dict[str, str]]:
    """Collect info about vector db.

    Args:
        infra_url: DeepFellow Infra URL, used as the embedding endpoint.
        original_env_content: The prior install's .env content, if any.
        vectordb_active: Whether a vector database should be configured.
        vectordb_type: Requested vector database type.
        vectordb_url: Requested vector database connection URL.
        vectordb_database_name: Requested vector database database/collection name.
        vectordb_username: Requested vector database username.
        vectordb_password: Requested vector database password.
        embedding_model: Requested embedding model.
        embedding_size: Requested embedding size.
        embedding_sparse: Whether to use sparse embeddings.
        default_vectordb_type: The type to show as the choice prompt's default (usually the prior
            install's type, falling back to vectordb_type's own CLI value).
        force_provided_type: Treat vectordb_type as explicitly provided even if it equals its own
            original_default - needed when it was merged in from a --template config value equal
            to that default. See deepfellow.common.echo.get_return_value.
        force_provided_url: Same as force_provided_type, for vectordb_url.
        force_provided_database_name: Same as force_provided_type, for vectordb_database_name.
        force_provided_model: Same as force_provided_type, for embedding_model.
        force_provided_size: Same as force_provided_type, for embedding_size. vectordb_username/
            vectordb_password have no --template config key of their own, so they need no
            equivalent flag.
    """
    if not should_use_vector_db(vectordb_active):
        return False, dict_to_env(
            {"provider": {"active": 0}, "embedding": {"active": 0}}, parent_key="DF_VECTOR_DATABASE"
        )

    original_env = original_env_content or {}

    # Ask embedding type before VDB type selection; model/size asked later (after VDB URL/credentials)
    embedding_type = _choose_embedding_type(original_env, embedding_model, embedding_sparse)

    # vectordb_type might be provided by the user or be default (VECTOR_DATABASE["provider"]["type"])
    # Ask user to choose type only if default value is provided.
    vectordb_type = echo.choice(
        "Choose the type of the vector database",
        from_args=vectordb_type,
        original_default=DEFAULT_VECTOR_DATABASE_TYPE,
        choices=ALLOWED_VECTOR_DB_TYPES,
        default=default_vectordb_type,
        force_provided=force_provided_type,
    )

    # Change default url if user changed the type of vector db
    if vectordb_type != DEFAULT_VECTOR_DATABASE_TYPE and vectordb_url == DEFAULT_VECTOR_DATABASE["provider"]["url"]:
        vectordb_url = VECTOR_DATABASES[vectordb_type]["provider"]["url"]

    # We do not ask detailed questions if we need to serve our version of vector DB
    if not is_custom_vectordb(
        vectordb_type,
        vectordb_url,
        vectordb_database_name,
    ):
        echo.info(f"DeepFellow will manage a {vectordb_type.capitalize()} instance.")
        vector_database = deepcopy(VECTOR_DATABASES[vectordb_type])
        vector_database["embedding"] = _build_embedding_config(
            embedding_type,
            infra_url,
            original_env,
            embedding_model,
            embedding_size,
            force_provided_model=force_provided_model,
            force_provided_size=force_provided_size,
        )
        # generate random login and password if not provided
        if not vectordb_username:
            vector_database["provider"]["user"] = vectordb_username = str(
                original_env.get("df_vector_database", {}).get("provider", {}).get("user") or generate_password(8)
            )
        if not vectordb_password:
            vector_database["provider"]["password"] = vectordb_password = original_env.get(
                "df_vector_database", {}
            ).get("provider", {}).get("password") or generate_password(12)

        return False, dict_to_env(vector_database, parent_key="DF_VECTOR_DATABASE")

    # Ask user the detailed questions, handling if setting is provided via args is solved in prompt
    original_provider = original_env.get("df_vector_database", {}).get("provider", {})

    provider = {
        "active": 1,
        "type": vectordb_type,
        "url": echo.prompt_until_valid(
            f"Provide {vectordb_type.capitalize()} instance URL",
            validate_url,
            default=original_provider.get("url", vectordb_url),
            from_args=vectordb_url,
            original_default=VECTOR_DATABASES[vectordb_type]["provider"]["url"],
            force_provided=force_provided_url,
        ),
    }

    if vectordb_type == "milvus":
        provider |= configure_milvus_specific_fields(
            original_provider,
            vectordb_database_name,
            vectordb_username,
            vectordb_password,
            force_provided_database_name=force_provided_database_name,
        )

    # Ask model/size after URL and credentials
    embedding = _build_embedding_config(
        embedding_type,
        infra_url,
        original_env,
        embedding_model,
        embedding_size,
        force_provided_model=force_provided_model,
        force_provided_size=force_provided_size,
    )

    return True, dict_to_env({"provider": provider, "embedding": embedding}, parent_key="DF_VECTOR_DATABASE")


def configure_infra(
    infra_api_key: str | None,
    infra_url: str,
    original_env: dict[str, Any] | None = None,
    *,
    force_provided_url: bool = False,
    force_provided_api_key: bool = False,
) -> dict[str, Any]:
    """Configure single infra.

    Args:
        infra_api_key: Requested DeepFellow Infra API key.
        infra_url: Requested DeepFellow Infra URL.
        original_env: The prior install's .env content, if any.
        force_provided_url: Treat infra_url as explicitly provided even if it equals its own
            original_default - needed when infra_url was merged in from a --template config
            value equal to that default, which would otherwise be indistinguishable from
            "nothing was provided" and prompt anyway. See deepfellow.common.echo.get_return_value.
        force_provided_api_key: Same as force_provided_url, for infra_api_key.

    Raises:
        typer.BadParameter: If the resolved URL fails ``validate_url``, or the resolved API key
            is empty (in non-interactive mode; interactively, ``echo.prompt_until_valid`` retries
            instead).
    """
    infra = {}
    original_env = original_env or {}

    infra["DF_INFRA__URL"] = echo.prompt_until_valid(
        "Provide DeepFellow Infra URL",
        validate_url,
        error_message="Invalid DeepFellow Infra URL. Please try again.",
        from_args=infra_url,
        original_default=DF_INFRA_URL,
        default=(original_env or {}).get("df_infra", {}).get("url", infra_url),
        force_provided=force_provided_url,
    )

    infra["DF_INFRA__API_KEY"] = echo.prompt_until_valid(
        "Provide Deepfellow Infra API KEY",
        validation=validate_truthy,
        from_args=infra_api_key,
        original_default=None,
        default=original_env.get("df_infra", {}).get("api_key") or "",
        password=True,
        force_provided=force_provided_api_key,
    )
    return infra


def _resolve_mongo_volume_conflict(directory: Path) -> None:
    """Let the user choose how to handle a stale Mongo volume before generating new credentials.

    MongoDB only applies MONGO_INITDB_ROOT_* on first init of an empty data directory. If the
    'mongo' Docker volume survived from an earlier install (e.g. after 'server uninstall', which
    removes .env but not volumes) while .env itself was lost, the fresh credentials configure_mongo()
    is about to generate would guarantee a runtime authentication failure, and there is no
    secondary store to recover the old ones from. Offer the choice explicitly instead of picking
    for the user: wipe the volume so the new credentials will work, or abort so they can
    investigate or restore the original .env first. A plain --non-interactive run still aborts by
    default (echo.confirm can't prompt, so it takes default=False) - only an explicit --yes
    authorizes removing the volume without asking, the same escape hatch prune() and the sudo rm
    retry already use for other destructive actions.
    """
    volume_name = resolve_compose_volume_name(directory, "mongo")
    if volume_name is None or not volume_exists(volume_name):
        return

    echo.warning(
        f"A MongoDB data volume ('{volume_name}') from a previous install already exists, but no "
        "matching credentials were found in .env. Generating new credentials without removing "
        "this volume is guaranteed to cause a MongoDB authentication failure at startup."
    )
    if not (
        state.yes
        or echo.confirm(f"Remove the existing volume '{volume_name}' now so new credentials will work?", default=False)
    ):
        echo.error(
            f"Installation aborted. Restore the original .env, or remove '{volume_name}' yourself "
            "and re-run, before trying again."
        )
        raise typer.Exit(1)

    try:
        remove_volume(volume_name)
    except DockerError as exc:
        echo.error(f"Failed to remove stale MongoDB volume '{volume_name}': {exc}")
        reraise_if_debug(exc)


def configure_mongo(
    directory: Path,
    custom: bool,
    mongo_user: str,
    mongo_password: str,
    mongo_url: str = DF_MONGO_URL,
    mongo_db: str = DF_MONGO_DB,
    original_env: dict[str, Any] | None = None,
    mongo_port: int = DF_MONGO_PORT,
) -> dict[str, str]:
    """Collect info about MongoDB."""
    original_env = original_env or {}
    mongo_config = {
        "DF_MONGO_URL": mongo_url,
        "DF_MONGO_USER": mongo_user,
        "DF_MONGO_PASSWORD": mongo_password,
        "DF_MONGO_DB": mongo_db,
    }
    if custom:
        mongo_config["DF_MONGO_URL"] = echo.prompt_until_valid(
            "Provide host:port for MongoDB e.g. 192.168.1.5:27017",
            validate_connection_string,
            from_args=mongo_url,
            original_default=DF_MONGO_URL,
            default=original_env.get("df_mongo_url"),
        )
        mongo_config["DF_MONGO_DB"] = echo.prompt_until_valid(
            "Provide database name for MongoDB",
            validate_truthy,
            from_args=mongo_db,
            original_default=DF_MONGO_DB,
            default=original_env.get("df_mongo_db"),
        )
        mongo_config["DF_MONGO_USER"] = echo.prompt_until_valid(
            "Provide username for MongoDB",
            validate_truthy,
            from_args=mongo_user,
            original_default="",
            default=original_env.get("df_mongo_user"),
        )
        mongo_config["DF_MONGO_PASSWORD"] = echo.prompt_until_valid(
            "Provide password for MongoDB",
            validate_truthy,
            from_args=mongo_password,
            original_default="",
            default=original_env.get("df_mongo_password"),
            password=True,
        )
    else:
        # Preserve existing admin credentials on reconfigure; on a fresh install with none to
        # preserve, check first for a stale Mongo volume that would reject freshly generated ones
        # (may prompt to remove it, or abort - see _resolve_mongo_volume_conflict).
        existing_admin_user = original_env.get("df_mongo_initdb_root_username")
        existing_admin_password = original_env.get("df_mongo_initdb_root_password")
        if not existing_admin_user or not existing_admin_password:
            _resolve_mongo_volume_conflict(directory)

        mongo_admin_user = existing_admin_user or generate_password(12)
        mongo_admin_password = existing_admin_password or generate_password(24)
        mongo_config |= {
            "DF_MONGO_INITDB_ROOT_USERNAME": mongo_admin_user,
            "DF_MONGO_INITDB_ROOT_PASSWORD": mongo_admin_password,
        }

        if not mongo_user:
            mongo_config["DF_MONGO_USER"] = original_env.get("df_mongo_user") or generate_password(8)
        if not mongo_password:
            mongo_config["DF_MONGO_PASSWORD"] = original_env.get("df_mongo_password") or generate_password(12)

        mongo_config["DF_MONGO_PORT"] = str(mongo_port)

        # Store the create user script
        init_mongo_path = directory / "init-mongo.sh"
        try:
            init_mongo_path.write_text(MONGO_DB_INIT_SH)
            init_mongo_path.chmod(0o755)
        except OSError as exc:
            echo.error(f"Unable to write {init_mongo_path.as_posix()}: {exc}.")
            reraise_if_debug(exc)

        echo.info("A default MongoDB setup is created.")

    return mongo_config


@dataclass
class OtelConfig:
    envs: dict[str, Any]
    docker_compose: dict[str, Any]


def configure_otel(
    directory: Path, otel_url: str | None, original_env: dict[str, Any] | None, otel_local: bool = False
) -> OtelConfig:
    """Configure Open Telemetry.

    When ``otel_local`` is set, configure a local debug-only collector without any prompts:
    add the otel-collector service to compose and write the debug-only collector config. The
    written config matches the interactive "run locally" + "no Elasticsearch" path, but the
    prompts and the post-write review warning are skipped. Mutual exclusion with ``otel_url``
    is enforced by the caller (``install()``); when ``otel_local`` is set, ``otel_url`` is ignored.

    Raises:
        typer.BadParameter: If ``otel_url`` is given directly (not via the interactive prompt,
            which validates it itself) and is not a valid URL.
    """
    original_env = original_env or {}
    docker_compose = {}
    envs = {}

    if otel_url:
        validate_url(otel_url)

    config_file: Path = directory / "otel-collector-config.yaml"

    if otel_local:
        debug_config = deepcopy(OTEL_COLLECTOR_CONFIG_DEBUG_ONLY)
        save_compose_file(debug_config, config_file, quiet=True, file_info="Open Telemetry collector configuration")

        return OtelConfig(
            envs={"DF_OTEL_EXPORTER_OTLP_ENDPOINT": DEFAULT_OTEL_URL, "DF_OTEL_TRACING_ENABLED": "true"},
            docker_compose=DOCKER_COMPOSE_OTEL_COLLECTOR,
        )

    existing_otel_config: dict[str, Any] = load_compose_file(config_file)
    prev_endpoint: str = existing_otel_config.get("exporters", {}).get("elasticsearch", {}).get("endpoint")
    prev_traces_index: str = existing_otel_config.get("exporters", {}).get("elasticsearch", {}).get("traces_index")
    prev_username: str = (
        existing_otel_config.get("extensions", {}).get("basicauth", {}).get("client_auth", {}).get("username")
    )
    prev_password: str = (
        existing_otel_config.get("extensions", {}).get("basicauth", {}).get("client_auth", {}).get("password")
    )

    if not otel_url:
        echo.info("DeepFellow Server might use an Open Telemetry.")
        if echo.confirm("Do you have an Open Telemetry server ready?"):
            otel_url = echo.prompt_until_valid(
                "Provide OTL url",
                default=original_env.get("df_otel_exporter_otlp_endpoint", DEFAULT_OTEL_URL),
                validation=validate_url,
            )
        elif echo.confirm(
            "Do you want to run Open Telemetry from this machine?",
            default=config_file.exists(),
        ):
            docker_compose = DOCKER_COMPOSE_OTEL_COLLECTOR
            otel_url = DEFAULT_OTEL_URL
            echo.info("Let's configure Open Telemetry")
            if echo.confirm("Do you want to export to Elasticsearch?", default=False):
                otel_config: dict[str, Any] = deepcopy(OTEL_COLLECTOR_CONFIG)
                otel_config["exporters"]["elasticsearch"]["endpoint"] = echo.prompt_until_valid(
                    "Provide your ElasticSearch endpoint", validation=validate_url, default=prev_endpoint
                )
                otel_config["exporters"]["elasticsearch"]["traces_index"] = echo.prompt_until_valid(
                    "Provide traces index", validation=validate_truthy, default=prev_traces_index
                )
                otel_config["extensions"]["basicauth"]["client_auth"]["username"] = echo.prompt_until_valid(
                    "Provide username", validation=validate_username, default=prev_username
                )
                otel_config["extensions"]["basicauth"]["client_auth"]["password"] = echo.prompt_until_valid(
                    "Provide password", validation=validate_truthy, password=True, default=prev_password
                )
            else:
                otel_config = deepcopy(OTEL_COLLECTOR_CONFIG_DEBUG_ONLY)
            save_compose_file(otel_config, config_file, quiet=True, file_info="Open Telemetry collector configuration")
            echo.warning(
                f"Open Telemetry configuration stored in file:\n{config_file}\n"
                "Please review its content before starting the DeepFellow Server."
            )

    envs = {"DF_OTEL_EXPORTER_OTLP_ENDPOINT": otel_url, "DF_OTEL_TRACING_ENABLED": "true"} if otel_url else {}

    return OtelConfig(
        envs=envs,
        docker_compose=docker_compose,
    )


@dataclass
class FalkorDBConfig:
    envs: dict[str, Any]
    docker_compose: dict[str, Any]


def should_use_falkordb(falkordb_active: bool) -> bool:
    """Check if server should configure the Knowledge Graph's FalkorDB instance."""
    if not falkordb_active:
        return False
    return echo.confirm("Do you want to enable the Knowledge Graph (FalkorDB) feature?", default=falkordb_active)


def is_custom_falkordb(falkordb_url: str) -> bool:
    """Check if user wants to connect an existing FalkorDB instance instead of a local one."""
    if falkordb_url != DF_FALKORDB_URL:
        return True
    return not echo.confirm("Install a local FalkorDB for DeepFellow Server?", default=True)


def _split_falkordb_host_port(value: str) -> tuple[str, str]:
    """Split a validated host[:port] connection string into (host, port)."""
    host, _, port = value.partition(":")
    return host, port or str(DF_FALKORDB_PORT)


def configure_falkordb(
    falkordb_active: bool,
    falkordb_url: str,
    falkordb_username: str,
    falkordb_password: str,
    original_env: dict[str, Any] | None = None,
) -> FalkorDBConfig:
    """Collect info about the Knowledge Graph's FalkorDB instance."""
    original_env = original_env or {}

    if not should_use_falkordb(falkordb_active):
        return FalkorDBConfig(envs={"DF_GRAPH__ENABLED": "false"}, docker_compose={})

    if not is_custom_falkordb(falkordb_url):
        falkordb_password = falkordb_password or str(original_env.get("df_graph__password") or generate_password(12))
        host, port = _split_falkordb_host_port(DF_FALKORDB_URL)
        echo.info("A default FalkorDB setup is created.")
        return FalkorDBConfig(
            envs={
                "DF_GRAPH__ENABLED": "true",
                "DF_GRAPH__HOST": host,
                "DF_GRAPH__PORT": port,
                "DF_GRAPH__USERNAME": "",
                "DF_GRAPH__PASSWORD": falkordb_password,
            },
            docker_compose=DOCKER_COMPOSE_FALKORDB,
        )

    stored_host = original_env.get("df_graph__host")
    stored_port = original_env.get("df_graph__port", DF_FALKORDB_PORT)
    stored_default = f"{stored_host}:{stored_port}" if stored_host else falkordb_url
    falkordb_url = echo.prompt_until_valid(
        "Provide host:port for FalkorDB e.g. 192.168.1.5:6379",
        validate_connection_string,
        from_args=falkordb_url,
        original_default=DF_FALKORDB_URL,
        default=stored_default,
    )
    host, port = _split_falkordb_host_port(falkordb_url)

    return FalkorDBConfig(
        envs={
            "DF_GRAPH__ENABLED": "true",
            "DF_GRAPH__HOST": host,
            "DF_GRAPH__PORT": port,
            "DF_GRAPH__USERNAME": falkordb_username or str(original_env.get("df_graph__username") or ""),
            "DF_GRAPH__PASSWORD": echo.prompt_until_valid(
                "Provide FalkorDB password",
                validate_truthy,
                from_args=falkordb_password,
                original_default="",
                default=original_env.get("df_graph__password", ""),
                password=True,
            ),
        },
        docker_compose={},
    )
