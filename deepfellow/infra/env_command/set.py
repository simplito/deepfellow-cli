# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra env set command."""

from pathlib import Path
from typing import Any

import httpx
import typer

from deepfellow.common.defaults import DF_INFRA_STORAGE_DIR
from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.install import assert_docker
from deepfellow.infra.utils.docker import start_infra, stop_infra
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


def _resolved_env_name(env_name: str, df_prefix: bool) -> str:
    """Return the env var name exactly as `env_set` will write it, for comparison against config.json fields."""
    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        env_name = f"DF_{env_name}"
    return env_name


def _config_json_exists(directory: Path) -> bool:
    """Best-effort check for whether config.json has already been seeded on this infra install.

    Only meaningful when infra isn't running, since that's when `_dynamic_field_name` can't query
    the admin API. Existence alone doesn't tell us whether the specific variable being set is one
    of the fields that migrated to config.json — only the admin API knows that — so this is used
    for a warning, not to block the write.
    """
    env_file = directory / ".env"
    storage_dir = env_get(env_file, "DF_INFRA_STORAGE_DIR", should_raise=False) or str(DF_INFRA_STORAGE_DIR)
    return (Path(storage_dir) / "config.json").is_file()


def _dynamic_field_name(directory: Path, env_name: str) -> str | None:
    """Return the config.json field name if `env_name` is dynamic config on the running instance.

    Infra only seeds config.json from `.env` the first time it starts; once config.json exists,
    the running instance never reads `.env` again for those fields, so setting one via `.env` and
    restarting silently has no effect. Only checked while infra is already running — before the
    first start, `.env` is still the real seed for config.json, so writing it is correct.

    Best-effort: if infra isn't running, or the admin API can't be reached, returns None so the
    caller falls back to the plain `.env` write.
    """
    if not is_service_running("infra", cwd=directory):
        return None

    env_file = directory / ".env"
    infra_port = env_get(env_file, "DF_INFRA_PORT", should_raise=False)
    admin_api_key = env_get(env_file, "DF_INFRA_ADMIN_API_KEY", should_raise=False)
    if not infra_port or not admin_api_key:
        return None

    try:
        response = httpx.get(
            f"http://localhost:{infra_port}/admin/config",
            headers={"Authorization": f"Bearer {admin_api_key}"},
            timeout=5.0,
        )
        response.raise_for_status()
        config: dict[str, Any] = response.json()
    except httpx.HTTPError:
        return None

    for entry in config.get("entries", []):
        if entry.get("key") == env_name and entry.get("is_editable"):
            field_name = entry.get("field_name")
            return str(field_name) if field_name else None

    return None


@app.command()
def set(
    directory: Path = directory_option(),
    env_name: str = typer.Argument(..., help="Name of the environment variable", callback=lambda x: x.upper()),
    env_value: str = typer.Argument("", help="Value of the environment variable"),
    df_prefix: bool = typer.Option(True, help="Add DF_ prefix if not provided?"),
    no_restart: bool = typer.Option(False, "--no-restart", help="Skip restarting the infra stack after the change."),
) -> None:
    """Set environment configuration."""
    check_infra_directory(directory)
    assert_docker()

    resolved_name = _resolved_env_name(env_name, df_prefix)
    field_name = _dynamic_field_name(directory, resolved_name)
    if field_name:
        echo.error(
            f"{resolved_name} is dynamic configuration stored in config.json. Writing it to .env has no effect "
            f"once Infra is running. Use `deepfellow infra config set {field_name}=<value>` instead."
        )
        raise typer.Exit(1)
    if not is_service_running("infra", cwd=directory) and _config_json_exists(directory):
        echo.warning(
            "Infra isn't running, so I can't check whether this variable is dynamic configuration stored in "
            "config.json. config.json already exists on this install, though — if it was migrated there, this "
            "write will have no effect once Infra starts. Start Infra and use `deepfellow infra config set` "
            "if unsure."
        )

    env_set(directory / ".env", env_name, env_value, df_prefix)
    if not no_restart and echo.confirm("Restart the infra now to apply the change?", default=True):
        echo.info("Restarting the infra...")
        stop_infra(directory)
        start_infra(directory)
        echo.success("Infra restarted successfully.")
