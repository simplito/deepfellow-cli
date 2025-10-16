"""Default config values."""

from pathlib import Path
from typing import Any

DF_DEEPFELLOW_DIRECTORY = Path.home() / ".deepfellow"

DF_CLI_CONFIG_PATH = DF_DEEPFELLOW_DIRECTORY / "config-cli.json"

DF_INFRA_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "infra"
DF_INFRA_REPO = "ssh://git@gitlab2.simplito.com:1022/df/deepfellow-infra.git"
DF_INFRA_CONFIG_PATH = Path("config/infra_config.toml")
DF_INFRA_IMAGE = "gitlab2.simplito.com:5050/df/deepfellow-infra:latest"
DF_INFRA_PORT = "9091"
DF_INFRA_DOCKER_NETWORK = "deepfellow-infra-net"
DF_INFRA_STORAGE_DIR = DF_INFRA_DIRECTORY / "storage"

DF_SERVER_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "server"
DF_SERVER_REPO = "ssh://git@gitlab2.simplito.com:1022/df/df-server-new.git"
DF_SERVER_IMAGE = "gitlab2.simplito.com:5050/df/df-server-new:latest"
DF_SERVER_PORT = "8086"

DF_MONGO_URL = "mongo:27017"
DF_MONGO_USER = "deepfellow-usr"
DF_MONGO_PASSWORD = "some-fake-password"
DF_MONGO_DB = "deepfellow"

API_ENDPOINTS = {"openai": {"url": "https://api.openai.com", "api_key": "some-fake-key", "name": "openai"}}

DF_VECTOR_DATABASE_URL = "http://milvus:19530"
VECTOR_DATABASE: dict[str, Any] = {
    "provider": {
        "active": 1,
        "type": "milvus",
        "url": DF_VECTOR_DATABASE_URL,
        "db": "deepfellow",
        "user": "deepfellow_usr",
        "password": "some-fake-password",
    },
    "embedding": {"active": 1, "endpoint": "openai", "model": "text-embedding-3-small", "size": "1536"},
}
DF_ADMIN_KEY = "some-admin-key"
