# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.


"""Version reporting for CLI and installed services."""

import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import DF_INFRA_DIRECTORY, DF_SERVER_DIRECTORY


def _run_git(*git_args: str) -> str | None:
    """Run a git command in the CLI source tree and return its stripped stdout.

    Only consults git when running from a DeepFellow source checkout, detected by a
    ``.git`` directory at the repository root (two levels above this package). This
    deliberately avoids letting git walk up the directory tree, so an installed
    package living inside an unrelated repository never reports that repo's data.
    Returns None when not in the source tree, when git is unavailable, or when the
    command fails.
    """
    repo_root = Path(__file__).resolve().parents[2]
    if not (repo_root / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *git_args],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def cli_version() -> str:
    """Return the CLI version.

    Resolves a real version number first — the git tag on the current commit, then the
    installed package metadata — and only falls back to the short commit hash (and
    finally 'unknown') when no version number is available.
    """
    tag = _run_git("describe", "--tags", "--exact-match")
    if tag:
        return tag.removeprefix("v")
    try:
        return _pkg_version("deepfellow-cli")
    except PackageNotFoundError:
        pass
    commit = _run_git("rev-parse", "--short", "HEAD")
    return commit or "unknown"


def _service_version(service_dir: Path, image_key: str) -> str | None:
    """Return installed service version from its image tag in .env, or None if not installed."""
    if not service_dir.is_dir():
        return None
    image = read_env_file_to_dict(service_dir / ".env").get(image_key, "")
    if not isinstance(image, str) or ":" not in image:
        return "unknown"
    return image.rsplit(":", 1)[1].removeprefix("v")


def version() -> None:
    """Show DeepFellow CLI, Infra, and Server version if installed."""
    print(f"DeepFellow CLI {cli_version()}")  # noqa: T201

    infra = _service_version(DF_INFRA_DIRECTORY, "df_infra_image")
    if infra is not None:
        print(f"DeepFellow Infra {infra}")  # noqa: T201

    server = _service_version(DF_SERVER_DIRECTORY, "df_server_image")
    if server is not None:
        print(f"DeepFellow Server {server}")  # noqa: T201
