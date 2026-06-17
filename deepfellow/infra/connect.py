# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra connect command."""

import time
from json import JSONDecodeError
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
import typer

from deepfellow.common.docker import is_service_running
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.system import run
from deepfellow.common.validation import validate_url
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()

_VERIFY_TIMEOUT = 10
_VERIFY_INTERVAL = 1
_LOCALHOST_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _is_localhost_url(url: str) -> bool:
    """Return True if the URL points to a localhost address."""
    try:
        return urlparse(url).hostname in _LOCALHOST_HOSTNAMES
    except Exception:
        return False


def http_to_ws_converter(url: str) -> str:
    """Return http -> ws and https -> wss conversion."""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        scheme = "wss" if parsed.scheme == "https" else "ws"
        url = urlunparse(parsed._replace(scheme=scheme))
    return url


class _VerifyResult:
    CONNECTED = "connected"
    TIMEOUT = "timeout"
    OUTDATED = "outdated"
    LEGACY = "legacy"


def _verify_parent_connection(local_infra_url: str, admin_api_key: str) -> str:
    """Poll the local mesh topology until a parent ancestor appears as the root node.

    Returns one of _VerifyResult constants.
    """
    topology_url = f"{local_infra_url}/admin/mesh/topology"
    headers = {"Authorization": f"Bearer {admin_api_key}"}
    deadline = time.monotonic() + _VERIFY_TIMEOUT
    non_json_count = 0
    got_valid_json = False

    while time.monotonic() < deadline:
        try:
            response = httpx.get(topology_url, headers=headers, timeout=5)
            if response.status_code == 200:
                topology = response.json()
                got_valid_json = True
                # Root node has you_are_here=False when a parent ancestor exists above us
                if topology and not topology[0].get("you_are_here", True):
                    return _VerifyResult.CONNECTED
                non_json_count = 0
        except httpx.HTTPError:
            pass
        except JSONDecodeError:
            non_json_count += 1
            if non_json_count >= 3:
                return _VerifyResult.OUTDATED
        time.sleep(_VERIFY_INTERVAL)

    # Topology returned valid JSON throughout but never showed a parent. This happens
    # when the parent uses the old API (returns "OK" instead of InitResponse with ancestors).
    if got_valid_json:
        return _VerifyResult.LEGACY

    return _VerifyResult.TIMEOUT


def _logs_show_connection(directory: Path) -> bool:
    """Return True if infra logs confirm a WebSocket connection was established and is still active."""
    try:
        cmd = ["docker", "compose", "logs", "infra", "--tail=100", "--no-color"]
        logs = run(cmd, cwd=directory, capture_output=True) or ""
        lines = logs.splitlines()
        setup_idx = max((i for i, line in enumerate(lines) if "WS client setup finished" in line), default=-1)
        disconnect_idx = max((i for i, line in enumerate(lines) if "WS client disconnected" in line), default=-1)
    except Exception:
        return False
    else:
        return setup_idx > disconnect_idx


@app.command()
def connect(
    directory: Path = directory_option(exists=True),
    parent_infra_url: str = typer.Argument(
        ..., help="Parent DeepFellow Infra address (DF_INFRA_MESH_URL).", callback=validate_url
    ),
    mesh_key: str = typer.Argument(..., help="DF_MESH_KEY of the Parent DeepFellow Infra."),
) -> None:
    """Connect two Infras together. This infra is child."""
    check_infra_directory(directory)

    if not is_service_running("infra", cwd=directory):
        echo.error("DeepFellow Infra is not running")
        echo.info("Call `deepfellow infra start`")
        raise typer.Exit(1)

    parent_infra_url = http_to_ws_converter(parent_infra_url)

    if _is_localhost_url(parent_infra_url):
        suggested = parent_infra_url.replace("127.0.0.1", "host.docker.internal").replace(
            "localhost", "host.docker.internal"
        )
        echo.error(
            f"The parent Infra URL {parent_infra_url} uses a localhost address. "
            "This Infra runs inside Docker and cannot reach the host via 127.0.0.1 or localhost. "
            f"Use host.docker.internal instead, e.g. {suggested}"
        )
        raise typer.Exit(1)

    env_file = directory / ".env"
    original_parent_infra_url = env_get(env_file, "DF_CONNECT_TO_MESH_URL")

    if original_parent_infra_url:
        echo.info(f"Disconnecting from {original_parent_infra_url} ...")

    env_set(env_file, "DF_CONNECT_TO_MESH_URL", parent_infra_url)
    env_set(env_file, "DF_CONNECT_TO_MESH_KEY", mesh_key)

    echo.info("Restarting this instance DeepFellow Infra ...")
    run(["docker", "compose", "down"], cwd=directory, quiet=True)
    run(["docker", "compose", "up", "-d", "--remove-orphans"], cwd=directory, quiet=True)

    infra_port = env_get(env_file, "DF_INFRA_PORT", should_raise=False)
    admin_api_key = env_get(env_file, "DF_INFRA_ADMIN_API_KEY", should_raise=False)

    if infra_port and admin_api_key:
        echo.info("Verifying connection to parent Infra ...")
        result = _verify_parent_connection(f"http://localhost:{infra_port}", admin_api_key)
        if result == _VerifyResult.OUTDATED:
            echo.warning(
                "This Infra image is outdated and does not support mesh topology verification. "
                "Run `deepfellow infra update` to update. "
                "The connection may still be active — check with `deepfellow infra logs`."
            )
        elif result == _VerifyResult.LEGACY:
            if _logs_show_connection(directory):
                echo.warning(
                    f"The parent Infra at {parent_infra_url} uses a legacy API that does not return "
                    "ancestor information. Topology will not show the parent node. "
                    "Update the parent Infra to get full mesh visibility."
                )
            else:
                echo.error(
                    f"Could not verify connection to {parent_infra_url}. "
                    "Check the mesh_key and that both Infras can reach each other over the network. "
                    "Run `deepfellow infra logs` for details."
                )
                raise typer.Exit(1)
        elif result == _VerifyResult.TIMEOUT:
            echo.error(
                f"Could not verify connection to {parent_infra_url}. "
                "Check the mesh_key and that both Infras can reach each other over the network. "
                "Run `deepfellow infra logs` for details."
            )
            raise typer.Exit(1)

    echo.success(f"DeepFellow Infra is connected to another Infra at {parent_infra_url}")
