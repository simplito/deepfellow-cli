"""Configure methods."""

from dataclasses import dataclass
from typing import Any

import typer

from deepfellow.common.config import dict_to_env
from deepfellow.common.defaults import DF_MONGO_DB, DF_MONGO_PASSWORD, DF_MONGO_URL, DF_MONGO_USER, VECTOR_DATABASE
from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_truthy, validate_url


def configure_vector_db(custom: bool, infra_url: str, original_env: dict[str, Any] | None = None) -> dict[str, str]:
    """Collect info about vector db."""
    original_env = original_env or {}
    original_provider = original_env.get("df_vector_database", {}).get("provider", {})
    vector_db_config: dict[str, Any] = VECTOR_DATABASE
    if custom:
        vector_db_config["provider"].update(
            {
                "url": echo.prompt_until_valid(
                    "Provide Milvus provider URL", validate_url, default=original_provider.get("url")
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
                "model": echo.prompt("Provide the model for embedding", default=VECTOR_DATABASE["embedding"]["model"]),
                "size": echo.prompt("Provide the embedding size", default=VECTOR_DATABASE["embedding"]["size"]),
            }
        )

    return dict_to_env(vector_db_config, parent_key="DF_VECTOR_DATABASE")


def configure_infra() -> dict[str, Any]:
    """Configure single infra."""
    infra = {}

    correct = False
    while not correct:
        try:
            infra["DF_INFRA__URL"] = echo.prompt(
                "Provide DeepFellow Infra URL", default="http://infra:8086", validation=validate_url
            )
            correct = True
        except typer.BadParameter:
            echo.error("Invalid DeepFellow Infra URL. Please try again.")
            correct = False

    infra["DF_INFRA__API_KEY"] = echo.prompt_until_valid(
        "Provide Deepfellow Infra API KEY", validation=validate_truthy, password=True
    )
    return infra


@dataclass
class Infras:
    envs: dict[str, str]
    names: list[str]


def configure_mongo(custom: bool, original_env: dict[str, Any] | None = None) -> dict[str, str]:
    """Collect info about MongoDB."""
    original_env = original_env or {}
    mongo_config = {
        "DF_MONGO_URL": DF_MONGO_URL,
        "DF_MONGO_USER": DF_MONGO_USER,
        "DF_MONGO_PASSWORD": DF_MONGO_PASSWORD,
        "DF_MONGO_DB": DF_MONGO_DB,
    }
    if custom:
        mongo_config["DF_MONGO_URL"] = echo.prompt_until_valid(
            "Provide URL for MongoDB", validate_url, default=original_env.get("df_mongo_url")
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
