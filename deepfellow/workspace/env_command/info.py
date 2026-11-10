# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""workspace env info command."""

from pathlib import Path

import typer

from deepfellow.common.env import EnvMetadata, print_env_info
from deepfellow.workspace.utils.install import read_installed_env
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()

ENV_METADATA: dict[str, EnvMetadata] = {
    "DF_SERVER_URL": EnvMetadata(
        description="DeepFellow Server URL, including /v1, as the Workspace container reaches it."
    ),
    "DF_SERVER_API_KEY": EnvMetadata(description="DeepFellow Server project API key.", sensitive=True),
    "DF_SERVER_ORGANIZATION_ID": EnvMetadata(description="DeepFellow Server organization id."),
    "DF_SERVER_PROJECT_ID": EnvMetadata(description="DeepFellow Server project id."),
    "SMALL_MODEL": EnvMetadata(
        description="Small model served by DeepFellow Server, used for background tasks (session titles, "
        "suggestions, summarizing long conversations, ...)."
    ),
    "PUBLIC_URL": EnvMetadata(
        description="Origin browsers reach Workspace at. The default http://localhost:<port> follows DF_WORKSPACE_PORT."
    ),
    "APP_SECRET": EnvMetadata(
        description="Signs user sessions and encrypts stored MCP credentials. Cannot be changed with `env set`.",
        sensitive=True,
    ),
    "MCP_AUTH_TOKEN": EnvMetadata(
        description="Bearer token required on the /mcp endpoint (at least 16 characters). An empty value "
        "generates a new one.",
        sensitive=True,
    ),
    "TRUSTED_PROXY_ENABLED": EnvMetadata(
        description="true: trust X-Forwarded-For / X-Real-IP; enable only behind a reverse proxy that sets them."
    ),
    "BOOTSTRAP_ADMIN_NAME": EnvMetadata(description="Name of the initial admin account, created on first start."),
    "BOOTSTRAP_ADMIN_EMAIL": EnvMetadata(description="E-mail of the initial admin account."),
    "BOOTSTRAP_ADMIN_PASSWORD": EnvMetadata(
        description="Password of the initial admin account. Remove the BOOTSTRAP_ADMIN_* lines after the first login.",
        sensitive=True,
    ),
    "SMTP_HOST": EnvMetadata(description="SMTP server host, to send e-mails. Empty: e-mail is off."),
    "SMTP_PORT": EnvMetadata(description="SMTP server port. Default: 587."),
    "SMTP_SECURE": EnvMetadata(description="true: use TLS from the start of the connection (usually with port 465)."),
    "SMTP_USERNAME": EnvMetadata(description="SMTP username."),
    "SMTP_PASSWORD": EnvMetadata(description="SMTP password.", sensitive=True),
    "EMAIL_FROM_ADDRESS": EnvMetadata(description="Sender e-mail address."),
    "EMAIL_FROM_NAME": EnvMetadata(description="Sender name."),
    "MONGO_DB_URL": EnvMetadata(
        description="External MongoDB (a replica set). Empty: the Mongo installed with Workspace is used.",
        sensitive=True,
    ),
    "MONGO_DB_NAME": EnvMetadata(description="Database name in the external MongoDB."),
    "REDIS_URL": EnvMetadata(
        description="External Redis. Empty: the Redis installed with Workspace is used.", sensitive=True
    ),
    "DF_WORKSPACE_IMAGE": EnvMetadata(
        description="DeepFellow Workspace image. Cannot be changed with `env set`; use `workspace update`, which "
        "pulls the image first."
    ),
    "DF_WORKSPACE_PORT": EnvMetadata(description="Host port Workspace is published on."),
    "DF_WORKSPACE_BIND_ADDRESS": EnvMetadata(
        description="Host address the Workspace port is published on, e.g. 127.0.0.1 or [::1] (IPv6 is stored in "
        "brackets). Empty: all interfaces."
    ),
    "DF_WORKSPACE_DOCKER_NETWORK": EnvMetadata(description="Docker network shared with DeepFellow Server."),
    "DF_WORKSPACE_MONGO_PASSWORD": EnvMetadata(
        description="Password of the root user of the Mongo installed with Workspace. Cannot be changed with "
        "`env set`.",
        sensitive=True,
    ),
    "DF_WORKSPACE_MONGO_KEY": EnvMetadata(
        description="Replica-set keyfile of the Mongo installed with Workspace. Cannot be changed with `env set`.",
        sensitive=True,
    ),
}


@app.command()
def info(
    directory: Path = directory_option(),
    secret: bool = typer.Option(False, "--secret", help="Display sensitive values."),
    doc: bool = typer.Option(False, "--doc", help="Display environment variables documentation."),
) -> None:
    """Display the settings from the Workspace .env file."""
    check_workspace_directory(directory)

    print_env_info(
        "Information about DeepFellow Workspace:",
        ENV_METADATA,
        read_installed_env(directory),
        show_secret=secret,
        doc=doc,
        show_prefix=True,
    )
