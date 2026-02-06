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
    DF_INFRA_URL,
    DF_MONGO_DB,
    DF_MONGO_URL,
    DOCKER_COMPOSE_OTEL_COLLECTOR,
    MILVUS_DATABASE,
    OTEL_COLLECTOR_CONFIG,
    QDRANT_DATABASE,
    VECTOR_DATABASES,
)
from deepfellow.common.docker import save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.generate import generate_password
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
    """Check if user wants DeepFellow to create its own instance of vector database."""
    any_milvus_arg_provided = (
        vectordb_url != MILVUS_DATABASE["provider"]["url"]
        or vectordb_database_name != MILVUS_DATABASE["provider"]["db"]
    )

    if (vectordb_type == "qdrant" and (vectordb_url != QDRANT_DATABASE["provider"]["url"])) or (
        vectordb_type == "milvus" and any_milvus_arg_provided
    ):
        return True

    return echo.confirm("Do you have a vector DB ready?", default=False)


def configure_milvus_specific_fields(
    original_provider: dict[str, str],
    vectordb_database_name: str,
    vectordb_username: str | None,
    vectordb_password: str | None,
) -> dict[str, str]:
    """Configure fields specific for milvus."""
    return {
        "db": echo.prompt_until_valid(
            "Provide Milvus provider database name",
            validate_truthy,
            from_args=vectordb_database_name,
            original_default=MILVUS_DATABASE["provider"]["db"],
            default=original_provider.get("db", vectordb_database_name),
        ),
        "user": echo.prompt_until_valid(
            "Provide Milvus provider user",
            validate_truthy,
            from_args=vectordb_username,
            original_default=MILVUS_DATABASE["provider"]["user"],
            default=original_provider.get("user", vectordb_username),
        ),
        "password": echo.prompt_until_valid(
            "Provide Milvus provider password",
            validate_truthy,
            from_args=vectordb_password,
            original_default=MILVUS_DATABASE["provider"]["password"],
            default=original_provider.get("password", vectordb_password),
            password=True,
        ),
    }


def configure_embedding(
    infra_url: str,
    original_env: dict[str, Any],
    embedding_model: str,
    embedding_size: str,
) -> dict[str, str | int]:
    """Configure embedding fields."""
    original_embedding = original_env.get("df_vector_database", {}).get("embedding", {})

    return {
        # Embedding is always active if vector db is active
        "active": 1,
        "endpoint": infra_url,
        "model": echo.prompt(
            "Provide the model for embedding",
            from_args=embedding_model,
            original_default=DEFAULT_VECTOR_DATABASE["embedding"]["model"],
            default=original_embedding.get("model", embedding_model),
        ),
        "size": echo.prompt(
            "Provide the embedding size",
            from_args=embedding_size,
            original_default=DEFAULT_VECTOR_DATABASE["embedding"]["size"],
            default=original_embedding.get("size", embedding_size),
        ),
    }


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
) -> tuple[bool, dict[str, str]]:
    """Collect info about vector db."""
    if not should_use_vector_db(vectordb_active):
        return False, dict_to_env(
            {"provider": {"active": 0}, "embedding": {"active": 0}}, parent_key="DF_VECTOR_DATABASE"
        )

    # vectordb_type might be provided by the user or be default (VECTOR_DATABASE["provider"]["type"])
    # Ask user to choose type only if default value is provided.
    if vectordb_type == DEFAULT_VECTOR_DATABASE_TYPE:
        vectordb_type = echo.choice(
            "Choose the type of the vector database",
            choices=ALLOWED_VECTOR_DB_TYPES,
            default=DEFAULT_VECTOR_DATABASE_TYPE,
        )

    # Change default url if user changed the type of vector db
    if vectordb_type != DEFAULT_VECTOR_DATABASE_TYPE and vectordb_url == DEFAULT_VECTOR_DATABASE["provider"]["url"]:
        vectordb_url = VECTOR_DATABASES[vectordb_type]["provider"]["url"]

    original_env = original_env_content or {}

    # We do not ask detailed questions if we need to serve our version of vector DB
    if not is_custom_vectordb(
        vectordb_type,
        vectordb_url,
        vectordb_database_name,
    ):
        # update embedding fields
        vector_database = deepcopy(VECTOR_DATABASES[vectordb_type])
        vector_database["embedding"]["model"] = embedding_model
        vector_database["embedding"]["size"] = embedding_size
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
        ),
    }

    if vectordb_type == "milvus":
        provider |= configure_milvus_specific_fields(
            original_provider,
            vectordb_database_name,
            vectordb_username,
            vectordb_password,
        )

    embedding = configure_embedding(
        infra_url,
        original_env,
        embedding_model,
        embedding_size,
    )

    return True, dict_to_env({"provider": provider, "embedding": embedding}, parent_key="DF_VECTOR_DATABASE")


def configure_infra(infra_api_key: str, infra_url: str, original_env: dict[str, Any] | None = None) -> dict[str, Any]:
    """Configure single infra."""
    infra = {}
    original_env = original_env or {}

    correct = False
    while not correct:
        try:
            infra["DF_INFRA__URL"] = echo.prompt(
                "Provide DeepFellow Infra URL",
                from_args=infra_url,
                original_default=DF_INFRA_URL,
                default=(original_env or {}).get("df_infra", {}).get("url", infra_url),
                validation=validate_url,
            )
            correct = True
        except typer.BadParameter:
            echo.error("Invalid DeepFellow Infra URL. Please try again.")
            correct = False

    infra["DF_INFRA__API_KEY"] = echo.prompt_until_valid(
        "Provide Deepfellow Infra API KEY",
        validation=validate_truthy,
        from_args=infra_api_key,
        original_default=None,
        default=original_env.get("df_infra", {}).get("api_key"),
        password=True,
    )
    return infra


@dataclass
class Infras:
    envs: dict[str, str]
    names: list[str]


def configure_mongo(
    custom: bool,
    mongo_user: str,
    mongo_password: str,
    mongo_url: str = DF_MONGO_URL,
    mongo_db: str = DF_MONGO_DB,
    original_env: dict[str, Any] | None = None,
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
        if not mongo_user:
            mongo_config["DF_MONGO_USER"] = original_env.get("df_mongo_user") or generate_password(8)
        if not mongo_password:
            mongo_config["DF_MONGO_PASSWORD"] = original_env.get("df_mongo_password") or generate_password(12)
        echo.info("A default MongoDB setup is created.")

    return mongo_config


@dataclass
class OtelConfig:
    envs: dict[str, Any]
    docker_compose: dict[str, Any]


def configure_otel(directory: Path, otel_url: str | None, original_env: dict[str, Any] | None) -> OtelConfig:
    """Configure Open Telemetry."""
    original_env = original_env or {}
    docker_compose = {}
    envs = {}

    if not otel_url:
        echo.info("DeepFellow Server might use an Open Telemetry.")
        if echo.confirm("Do you have an Open Telemetry server ready?"):
            otel_url = echo.prompt_until_valid(
                "Provide OTL url",
                default=original_env.get("df_otel_exporter_orlp_endpoint", DEFAULT_OTEL_URL),
                validation=validate_url,
            )
        elif echo.confirm(
            "Do you want to run Open Telemetry from this machine?\n(You need an existing ElasticSearch server running)",
            default=False,
        ):
            config_file = directory / "otel-collector-config.yaml"
            docker_compose = DOCKER_COMPOSE_OTEL_COLLECTOR
            otel_url = DEFAULT_OTEL_URL
            # store Open Telemetry yaml config
            echo.info("Let's configure Open Telemetry")
            otel_config: dict[str, Any] = deepcopy(OTEL_COLLECTOR_CONFIG)
            otel_config["exporters"]["elasticsearch"]["endpoint"] = echo.prompt_until_valid(
                "Provide your ElasticSearch endpoint", validation=validate_url
            )
            otel_config["exporters"]["elasticsearch"]["traces_index"] = echo.prompt_until_valid(
                "Provide traces index", validation=validate_truthy
            )
            otel_config["extensions"]["basicauth"]["client_auth"]["username"] = echo.prompt_until_valid(
                "Provide username", validation=validate_username
            )
            otel_config["extensions"]["basicauth"]["client_auth"]["password"] = echo.prompt_until_valid(
                "Provide password", validation=validate_truthy, password=True
            )
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
