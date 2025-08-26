"""Default config values."""

from pathlib import Path

DF_DEEPFELLOW_DIRECTORY = Path.home() / ".deepfellow"

DF_CLI_CONFIG_PATH = DF_DEEPFELLOW_DIRECTORY / "config-cli.json"

DF_INFRA_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "infra"
DF_INFRA_REPO = "ssh://git@gitlab2.simplito.com:1022/df/deepfellow-infra.git"
DF_INFRA_CONFIG_PATH = Path("config/infra_config.toml")
DF_INFRA_IMAGE = "gitlab2.simplito.com:5050/df/deepfellow-infra:latest"

DF_SERVER_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "server"
DF_SERVER_REPO = "ssh://git@gitlab2.simplito.com:1022/df/df-server-new.git"

DF_MONGO_URL = "monger1.s24.simplito.com/deepfellow"
DF_MONGO_USER = "deepfellow-usr"
DF_MONGO_PASSWORD = "some-fake-password"
DF_MONGO_DB = "deepfellow"
DF_API_ENDPOINTS__OPENAI__URL = "https://api.openai.com"
DF_API_ENDPOINTS__OPENAI__API_KEY = "some-fake-key"
DF_API_ENDPOINTS__OPENAI__NAME = "openai"
DF_VECTOR_DATABASE__PROVIDER__ACTIVE = 1
DF_VECTOR_DATABASE__PROVIDER__TYPE = "milvus"
DF_VECTOR_DATABASE__PROVIDER__URL = "https://milvus.s24.simplito.com:443"
DF_VECTOR_DATABASE__PROVIDER__DB = "deepfellow"
DF_VECTOR_DATABASE__PROVIDER__USER = "deepfellow_usr"
DF_VECTOR_DATABASE__PROVIDER__PASSWORD = "some-fake-password"
DF_VECTOR_DATABASE__EMBEDDING__ACTIVE = 1
DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT = "openai"
DF_VECTOR_DATABASE__EMBEDDING__MODEL = "text-embedding-3-small"
DF_VECTOR_DATABASE__EMBEDDING__SIZE = "1536"
DF_ADMIN_KEY = "some-admin-key"
