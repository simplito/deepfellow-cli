# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""server info command."""

from typing import Any

import httpx
import typer

from deepfellow.common.config import dict_to_env, read_env_file, reveal_masked_paths
from deepfellow.common.echo import echo
from deepfellow.common.env import print_env_info
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.env_command.info import ENV_METADATA

app = typer.Typer()


def _ensure_dict(config: Any) -> None:
    """Raise if the admin API response isn't the expected dict shape."""
    if not isinstance(config, dict):
        raise TypeError("Unexpected response from Server admin API")


def _dynamic_config_values(server: str | None, secret: bool) -> dict[str, str]:
    """Fetch current dynamic config from the server's `/admin/config`.

    Resolved the same way `server config get` resolves its target: `server` (from `--server`) if
    given, otherwise the CLI's configured default server URL, and the user token stored locally.
    Unlike the env file view, this always talks to the server: it exits with an error if nothing
    is resolvable without prompting (no login flow is triggered), or the request fails for any
    reason (server down, unreachable, expired token, a non-JSON or unexpected response, ...).
    """
    resolved_server = server or state.cli_config.get("df_server_url")
    secrets_file = state.cli_secrets_file
    token = read_env_file(secrets_file).get("DF_USER_TOKEN") if secrets_file.is_file() else None

    if not resolved_server or not token:
        echo.error("No DeepFellow Server/user token configured. Pass --server or log in with `server login`.")
        raise typer.Exit(1)

    try:
        response = httpx.get(
            f"{resolved_server}/admin/config",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        response.raise_for_status()
        config: dict[str, Any] = response.json()
        _ensure_dict(config)

        if secret:
            reveal_masked_paths(
                config,
                lambda path: httpx.get(
                    f"{resolved_server}/admin/config/reveal/{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                ).json()["value"],
            )
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as exc:
        echo.error(f"Could not read DeepFellow Server configuration: {exc}")
        reraise_if_debug(exc)

    return dict_to_env(config)


@app.command()
def info(
    server: str | None = typer.Option(
        None, "--server", callback=validate_server, help="DeepFellow Server address, for reading dynamic config."
    ),
    secret: bool = typer.Option(
        False,
        "--secret",
        help="Display sensitive values.",
    ),
    doc: bool = typer.Option(
        False,
        "--doc",
        help="Display environment variables documentation.",
    ),
) -> None:
    """Display Server's current dynamic configuration (GET /admin/config)."""
    env_values = _dynamic_config_values(server, secret)

    print_env_info("Information about DeepFellow Server:", ENV_METADATA, env_values, show_secret=secret, doc=doc)
