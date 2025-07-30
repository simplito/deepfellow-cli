import os
from pathlib import Path

DF_CLI_CONFIG_PATH = os.environ.get("DF_CLI_CONFIG_PATH") or Path.home() / ".deepfellow/config-cli.json"

DF_INFRA_DIRECTORY = os.environ.get("DF_INFRA_DIRECTORY") or Path.home() / ".deepfellow/infra"
DF_INFRA_REPO = os.environ.get("DF_INFRA_REPO") or "ssh://git@gitlab2.simplito.com:1022/df/deepfellow-infra.git"
DF_INFRA_CONFIG_PATH = os.environ.get("DF_INFRA_CONFIG_PATH") or Path("config/infra.json")
