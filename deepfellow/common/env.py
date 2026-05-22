# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helper do komend env."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.markup import escape

from deepfellow.common.config import read_env_file, save_env_file
from deepfellow.common.echo import echo


@dataclass(frozen=True)
class EnvMetadata:
    """Environment variable metadata."""

    description: str = ""
    sensitive: bool = False

    def render(self, key: str, value: str, show_secret: bool = False) -> str:
        """Return styled env name and value."""
        if not value:
            display = "[dim]undefined[/dim]"
        elif self.sensitive and not show_secret:
            display = "[dim]*****[/dim]"
        else:
            display = f"[yellow]{escape(value)}[/yellow]"

        styled_key = f"[cyan bold]{escape(key.removeprefix('DF_'))}[/]"
        return f"{styled_key}: {display}"


def env_set(
    env_file: Path,
    env_name: str,
    env_value: str,
    df_prefix: bool = True,
    should_raise: bool = True,
    quiet: bool = False,
    **kwargs: Any,
) -> None:
    """Set env value in the directpry/.env file."""
    if not env_file.is_file() and should_raise:
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs: dict[str, str] = {}

    if env_file.is_file():
        envs = read_env_file(env_file)

    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        echo.debug("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    envs[env_name] = env_value
    save_env_file(env_file, envs, quiet=quiet, **kwargs)


def env_get(
    env_file: Path, env_name: str, df_prefix: bool = True, should_raise: bool = True, default: str | None = None
) -> str | None:
    """Set env value in the directpry/.env file."""
    if not env_file.is_file() and should_raise:
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs: dict[str, str] = {}

    if env_file.is_file():
        envs = read_env_file(env_file)

    env_name = env_name.upper()
    if df_prefix and not env_name.startswith("DF_"):
        echo.debug("Added the DF_ prefix to the variable name")
        env_name = f"DF_{env_name}"

    return envs.get(env_name, default)


def print_env_info(
    header: str,
    env_metadata: dict[str, EnvMetadata],
    env_values: dict[str, str],
    show_secret: bool = False,
    doc: bool = False,
) -> None:
    """Print environment info or documentation via echo.info."""
    if doc:
        lines = ["Environment variables documentation:"]
        for key, meta in env_metadata.items():
            value = env_values.get(key, "")
            lines.append(meta.render(key, value, show_secret=show_secret))
            lines.append(f"[italic][grey50]{meta.description}[/grey50][/italic]")
    else:
        lines = [header]
        for k, v in env_values.items():
            env_meta = env_metadata.get(k, EnvMetadata())
            lines.append(env_meta.render(k, v, show_secret=show_secret))
    echo.info("\n".join(lines))


def get_envs_list(env_file: Path) -> list[str]:
    """Return a list of strings representing the envs."""
    if not env_file.is_file():
        echo.error(f"Environment file not found: {env_file}")
        raise typer.Exit(1)

    envs = read_env_file(env_file)
    return [f"{env}={value}" for env, value in envs.items()]
