# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server env set command."""

from pathlib import Path

import httpx
import typer

from deepfellow.common.config import dict_to_env, read_env_file
from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.state import state
from deepfellow.server.utils.docker import start_server, stop_server
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.storage import config_json_exists
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


def _resolved_env_name(env_name: str, df_prefix: bool) -> str:
    """Return the env var name exactly as `env_set` will write it, for comparison against config.json fields."""
    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        env_name = f"DF_{env_name}"
    return env_name


def _dynamic_field_name(directory: Path, env_name: str) -> str | None:
    """Return the config.json field name if `env_name` is dynamic config on the running instance.

    The server only seeds config.json from `.env` the first time it starts; once config.json
    exists, the running instance never reads `.env` again for those fields, so setting one via
    `.env` and restarting silently has no effect. Only checked while the server is already
    running — before the first start, `.env` is still the real seed for config.json, so writing
    it is correct.

    Best-effort: if the server isn't running, no user token is stored locally, or the admin API
    can't be reached, returns None so the caller falls back to the plain `.env` write.
    """
    if not is_service_running("server", cwd=directory):
        return None

    port = env_get(directory / ".env", "DF_SERVER_PORT", should_raise=False)
    if not port:
        return None

    secrets_file = state.cli_secrets_file
    token = read_env_file(secrets_file).get("DF_USER_TOKEN") if secrets_file.is_file() else None
    if not token:
        return None

    try:
        response = httpx.get(
            f"http://localhost:{port}/admin/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        response.raise_for_status()
        config = response.json()
    except httpx.HTTPError:
        return None

    dynamic_envs = dict_to_env(config)
    if env_name not in dynamic_envs:
        return None

    return env_name.removeprefix("DF_").lower()


@app.command()
def set(
    directory: Path = directory_option(),
    env_name: str = typer.Argument(..., help="Name of the environment variable", callback=lambda x: x.upper()),
    env_value: str = typer.Argument("", help="Value of the environment variable"),
    df_prefix: bool = typer.Option(True, help="Add DF_ prefix if not provided?"),
    no_restart: bool = typer.Option(False, "--no-restart", help="Skip restarting the server stack after the change."),
) -> None:
    """Set environment configuration."""
    check_server_directory(directory)
    assert_docker()

    resolved_name = _resolved_env_name(env_name, df_prefix)
    field_name = _dynamic_field_name(directory, resolved_name)
    if field_name:
        echo.error(
            f"{resolved_name} is dynamic configuration stored in config.json. Writing it to .env has no effect "
            f"once the server is running. Use `deepfellow server config set {field_name}=<value>` instead."
        )
        raise typer.Exit(1)
    # Existence alone doesn't tell us whether this particular variable is one of the fields that
    # migrated to config.json - only the admin API knows that, and it's unreachable while the server
    # is down - so this warns rather than blocking the write.
    if not is_service_running("server", cwd=directory) and config_json_exists():
        echo.warning(
            "The server isn't running, so I can't check whether this variable is dynamic configuration stored "
            "in config.json. config.json already exists on this install, though — if it was migrated there, "
            "this write will have no effect once the server starts. Start the server and use "
            "`deepfellow server config set` if unsure."
        )

    env_set(directory / ".env", env_name, env_value, df_prefix)
    if not no_restart and echo.confirm("Restart the server now to apply the change?", default=True):
        echo.info("Restarting the server...")
        stop_server(directory)
        start_server(directory)
        echo.success("Server restarted successfully.")
