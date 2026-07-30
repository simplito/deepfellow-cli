# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra info command."""

from typing import Any

import httpx
import typer

from deepfellow.common.config import read_env_file, reveal_secret_entries
from deepfellow.common.echo import echo
from deepfellow.common.env import print_env_info
from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.infra.env_command.info import ENV_METADATA

app = typer.Typer()


def _ensure_dict(config: Any) -> None:
    """Raise if the admin API response isn't the expected dict shape."""
    if not isinstance(config, dict):
        raise TypeError("Unexpected response from Infra admin API")


def _dynamic_config_values(server: str | None, api_key: str | None, secret: bool) -> dict[str, str]:
    """Fetch current dynamic config from Infra's `/admin/config`.

    Resolved the same way `infra config get` resolves its target: `server`/`api_key` (from
    `--url`/`--api-key`) if given, otherwise the externally-configured Infra URL and the
    admin API key stored locally. Unlike the env file view, this always talks to Infra: it exits
    with an error if nothing is resolvable, or the request fails for any reason (Infra down,
    unreachable, wrong credentials, a non-JSON or unexpected response, ...).
    """
    config: dict[str, Any] = {}
    resolved_server = server or state.cli_config.get("df_infra_external_url")
    resolved_key = api_key
    if resolved_key is None:
        secrets_file = state.cli_secrets_file
        secrets = read_env_file(secrets_file) if secrets_file.is_file() else {}
        resolved_key = secrets.get("DF_INFRA_ADMIN_API_KEY")

    if not resolved_server or not resolved_key:
        echo.error("No DeepFellow Infra server/API key configured. Pass --url/--api-key or run `infra connect`.")
        raise typer.Exit(1)

    try:
        response = httpx.get(
            f"{resolved_server}/admin/config",
            headers={"Authorization": f"Bearer {resolved_key}"},
            timeout=5.0,
        )
        response.raise_for_status()
        config = response.json()
        _ensure_dict(config)

        if secret:
            reveal_secret_entries(
                config,
                lambda key: httpx.get(
                    f"{resolved_server}/admin/config/{key}/reveal",
                    headers={"Authorization": f"Bearer {resolved_key}"},
                    timeout=5.0,
                ).json()["value"],
            )
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as exc:
        echo.error(f"Could not read DeepFellow Infra configuration: {exc}")
        reraise_if_debug(exc)

    return {
        entry["key"]: str(entry["value"])
        for entry in config.get("entries", [])
        if entry.get("key") and entry.get("value") is not None
    }


@app.command()
def info(
    server: str | None = typer.Option(
        None, "--url", callback=validate_server, help="DeepFellow Infra address, for reading dynamic config."
    ),
    api_key: str | None = typer.Option(
        None, "--api-key", help="Infra Admin API Key to use, instead of the one currently stored locally."
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
    """Display Infra's current dynamic configuration (GET /admin/config)."""
    env_values = _dynamic_config_values(server, api_key, secret)

    if "DF_INFRA_URL" in env_values:
        env_values["DF_INFRA_MESH_URL"] = (
            env_values["DF_INFRA_URL"].replace("http://", "ws://").replace("https://", "wss://")
        )

    print_env_info("Information about DeepFellow Infra:", ENV_METADATA, env_values, show_secret=secret, doc=doc)
