"""Configure methods."""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from deepfellow.common.config import dict_to_env
from deepfellow.common.defaults import DF_MONGO_DB, DF_MONGO_PASSWORD, DF_MONGO_URL, DF_MONGO_USER, VECTOR_DATABASE
from deepfellow.common.echo import echo


def configure_vector_db(custom: bool, api_endpoints: list[str]) -> dict[str, str]:
    """Collect info about vector db."""
    vector_db_config = VECTOR_DATABASE
    if custom:
        vector_db_config["provider"].update(
            {
                "url": echo.prompt("Provide Milvus provider URL"),
                "db": echo.prompt("Provide Milvus provider database name"),
                "user": echo.prompt("Provide Milvus provider user"),
                "password": echo.prompt("Provide Milvus provider password", password=True),
            }
        )
    else:
        if not echo.confirm("Do you want to run Milvus from this machine?", default=True):
            vector_db_config = {"provider": {"active": 0}, "embedding": {"active": 0}}

    if int(vector_db_config["embedding"]["active"]) == 1:
        vector_db_config["embedding"]["endpoint"] = (
            api_endpoints[0]
            if len(api_endpoints) == 1
            else echo.prompt("Which API Endpoint should be used for embedding?", choices=api_endpoints)
        )
        vector_db_config["embedding"].update(
            {
                "model": echo.prompt("Provide the model for embedding", default=VECTOR_DATABASE["embedding"]["model"]),
                "size": echo.prompt("Provide the embedding size", default=VECTOR_DATABASE["embedding"]["size"])
            }
        )

    return dict_to_env(vector_db_config, parent_key="DF_VECTOR_DATABASE")


def configure_infra(name: str) -> dict[str, Any]:
    """Configure single infra."""
    infra = {"name": name}
    infra["url"] = echo.prompt("Provide API Endpoint URL")
    infra["api_key"] = echo.prompt("Provide API Endpoint API KEY", password=True)
    return infra


@dataclass
class Infras:
    envs: dict[str, str]
    names: list[str]


def configure_infras() -> Infras:
    """Collect info about infra."""
    all_infras_configured = False
    api_endpoints = {}

    while not all_infras_configured:
        api_endpoint_name = echo.prompt("Provide the name of your API Endpoint")
        api_endpoints[api_endpoint_name] = configure_infra(api_endpoint_name)
        all_infras_configured = not echo.confirm("Do you want to configure additional API Endpoint?")

    envs = dict_to_env(api_endpoints, parent_key="DF_API_ENDPOINTS")
    return Infras(envs=envs, names=list(api_endpoints.keys()))


def configure_mongo(custom: bool) -> dict[str, str]:
    """Collect info about MongoDB."""
    mongo_config = {
        "DF_MONGO_URL": DF_MONGO_URL,
        "DF_MONGO_USER": DF_MONGO_USER,
        "DF_MONGO_PASSWORD": DF_MONGO_PASSWORD,
        "DF_MONGO_DB": DF_MONGO_DB,
    }
    if custom:
        mongo_config["DF_MONGO_URL"] = echo.prompt("Provide URL for MongoDB")
        mongo_config["DF_MONGO_DB"] = echo.prompt("Provide database name for MongoDB")
        mongo_config["DF_MONGO_USER"] = echo.prompt("Provide username for MongoDB")
        mongo_config["DF_MONGO_PASSWORD"] = echo.prompt("Provide password for MongoDB", password=True)
    else:
        echo.info("A default MongoDB setup is created.")

    return mongo_config


def configure_admin_key(existing: str | None) -> str:
    """Generate a new admin key if required."""
    if existing is not None and echo.confirm(
        "There is an existing Admin Key in the env file. Do you want to keep it?", default=True
    ):
        return existing

    admin_key = str(uuid4())
    if echo.confirm("Admin key created. Is it safe to print it here?"):
        echo.info(f"ADMIN_KEY: {admin_key}")

    return admin_key
