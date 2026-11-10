# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path

import pytest

from deepfellow.workspace.utils.install import write_stack

INSTALLED_ENV: dict[str, str] = {
    "DF_SERVER_URL": "http://server:8000/v1",
    "DF_SERVER_API_KEY": "server-api-key",
    "DF_SERVER_ORGANIZATION_ID": "org",
    "DF_SERVER_PROJECT_ID": "proj",
    "SMALL_MODEL": "small",
    "PUBLIC_URL": "http://localhost:3000",
    "APP_SECRET": "app-secret-value",
    "MCP_AUTH_TOKEN": "mcp-Pa$word#1-1234567890",
    "DF_WORKSPACE_MONGO_PASSWORD": "mongo-password",
    "DF_WORKSPACE_MONGO_KEY": "mongo-keyfile",
    "DF_WORKSPACE_IMAGE": "hub.simplito.com/deepfellow/deepfellow-workspace:v0.7.0",
    "DF_WORKSPACE_PORT": "3000",
    "DF_WORKSPACE_BIND_ADDRESS": "",
    "DF_WORKSPACE_DOCKER_NETWORK": "net",
}


@pytest.fixture
def installed_env() -> dict[str, str]:
    return dict(INSTALLED_ENV)


@pytest.fixture
def workspace_dir(tmp_path: Path, installed_env: dict[str, str]) -> Path:
    write_stack(tmp_path, installed_env)
    return tmp_path
