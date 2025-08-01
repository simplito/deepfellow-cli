"""Default config values."""

from pathlib import Path

DF_CLI_CONFIG_PATH = Path.home() / ".deepfellow/config-cli.json"

DF_INFRA_DIRECTORY = Path.home() / ".deepfellow/infra"
DF_INFRA_REPO = "ssh://git@gitlab2.simplito.com:1022/df/deepfellow-infra.git"
DF_INFRA_CONFIG_PATH = Path("config/infra_config.toml")
