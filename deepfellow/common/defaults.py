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
