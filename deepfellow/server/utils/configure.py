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
    DEFAULT_OTEL_URL,
    DF_MONGO_DB,
    DF_MONGO_PASSWORD,
    DF_MONGO_URL,
    DF_MONGO_USER,
    DOCKER_COMPOSE_OTEL_COLLECTOR,
    OTEL_COLLECTOR_CONFIG,
    VECTOR_DATABASE,
)
from deepfellow.common.docker import save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_connection_string, validate_truthy, validate_url, validate_username


def configure_vector_db(
    custom: bool,
    infra_url: str,
    original_env: dict[str, Any] | None = None,
    vectordb_active: bool = bool(VECTOR_DATABASE["provider"]["active"]),
    vectordb_type: str = VECTOR_DATABASE["provider"]["type"],
    vectordb_url: str = VECTOR_DATABASE["provider"]["url"],
    vectordb_db: str = VECTOR_DATABASE["provider"]["db"],
    vectordb_user: str = VECTOR_DATABASE["provider"]["user"],
    vectordb_password: str = VECTOR_DATABASE["provider"]["password"],
    embedding: bool = bool(VECTOR_DATABASE["embedding"]["active"]),
    embedding_endpoint: str = VECTOR_DATABASE["embedding"]["endpoint"],
    embedding_model: str = VECTOR_DATABASE["embedding"]["model"],
    embedding_size: int = VECTOR_DATABASE["embedding"]["size"],
) -> dict[str, str]:
    """Collect info about vector db."""
    original_env = original_env or {}
    original_provider = original_env.get("df_vector_database", {}).get("provider", {})
    vector_db_config: dict[str, Any] = VECTOR_DATABASE
    vector_db_config = {
        "provider": {
            "active": vectordb_active,
            "type": vectordb_type,
            "url": vectordb_url,
            "db": vectordb_db,
            "user": vectordb_user,
            "password": vectordb_password,
        },
        "embedding": {
            "active": embedding,
            "endpoint": embedding_endpoint,
            "model": embedding_model,
            "size": embedding_size,
        },
    }
    if custom:
        vector_db_config["provider"].update(
            {
                "url": echo.prompt_until_valid(
                    "Provide Milvus instance URL", validate_url, default=original_provider.get("url")
                ),
                "db": echo.prompt_until_valid(
                    "Provide Milvus provider database name", validate_truthy, default=original_provider.get("db")
                ),
                "user": echo.prompt_until_valid(
                    "Provide Milvus provider user", validate_truthy, default=original_provider.get("user")
                ),
                "password": echo.prompt_until_valid("Provide Milvus provider password", validate_truthy, password=True),
            }
        )
    else:
        if not echo.confirm("Do you want to run Milvus from this machine?", default=True):
            vector_db_config = {"provider": {"active": 0}, "embedding": {"active": 0}}

    if int(vector_db_config["embedding"]["active"]) == 1:
        vector_db_config["embedding"]["endpoint"] = infra_url
        vector_db_config["embedding"].update(
            {
                "model": echo.prompt("Provide the model for embedding", default=vector_db_config["embedding"]["model"]),
                "size": echo.prompt("Provide the embedding size", default=vector_db_config["embedding"]["size"]),
            }
        )

    return dict_to_env(vector_db_config, parent_key="DF_VECTOR_DATABASE")


def configure_infra(infra_api_key: str, default_infra_url: str = "http://infra:8086") -> dict[str, Any]:
    """Configure single infra."""
    infra = {}

    correct = False
    while not correct:
        try:
            infra["DF_INFRA__URL"] = echo.prompt(
                "Provide DeepFellow Infra URL", default=default_infra_url, validation=validate_url
            )
            correct = True
        except typer.BadParameter:
            echo.error("Invalid DeepFellow Infra URL. Please try again.")
            correct = False

    infra["DF_INFRA__API_KEY"] = (
        infra_api_key
        if infra_api_key
        else echo.prompt_until_valid("Provide Deepfellow Infra API KEY", validation=validate_truthy, password=True)
    )
    return infra


@dataclass
class Infras:
    envs: dict[str, str]
    names: list[str]


def configure_mongo(
    custom: bool,
    original_env: dict[str, Any] | None = None,
    mongo_url: str = DF_MONGO_URL,
    mongo_user: str = DF_MONGO_USER,
    mongo_password: str = DF_MONGO_PASSWORD,
    mongo_db: str = DF_MONGO_DB,
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
            default=original_env.get("df_mongo_url"),
        )
        mongo_config["DF_MONGO_DB"] = echo.prompt_until_valid(
            "Provide database name for MongoDB", validate_truthy, default=original_env.get("df_mongo_db")
        )
        mongo_config["DF_MONGO_USER"] = echo.prompt_until_valid(
            "Provide username for MongoDB", validate_truthy, default=original_env.get("df_mongo_user")
        )
        mongo_config["DF_MONGO_PASSWORD"] = echo.prompt_until_valid(
            "Provide password for MongoDB", validate_truthy, password=True
        )
    else:
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
            default=True,
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

    envs = {"DF_OTEL_EXPORTER_OTLP_ENDPOINT": otel_url, "DF_OTEL_TRACING_ENABLED": "true"}

    return OtelConfig(
        envs=envs,
        docker_compose=docker_compose,
    )
