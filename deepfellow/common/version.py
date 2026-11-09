# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Version reporting for CLI and installed services."""

import re
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import DF_INFRA_DIRECTORY
from deepfellow.common.docker import DockerError, get_running_service_image, is_service_running_or_raise


def _repo_root() -> Path:
    """Return the directory that contains the `deepfellow` package.

    That is the repository root in a source checkout and `site-packages` in an installed package.
    """
    return Path(__file__).resolve().parents[2]


def is_source_checkout() -> bool:
    """Return whether the CLI runs from a DeepFellow source checkout.

    Detected by a ``.git`` entry only in the directory that contains the `deepfellow` package
    (see `_repo_root`). This deliberately avoids walking up the directory tree, so an installed
    package living inside an unrelated repository is not mistaken for a checkout.
    """
    return (_repo_root() / ".git").exists()


def _run_git(*git_args: str) -> str | None:
    """Run a git command in the CLI source tree and return its stripped stdout.

    Only consults git when running from a DeepFellow source checkout (see
    `is_source_checkout`), so an installed package never reports another repo's data.
    Returns None when not in the source tree, when git is unavailable, or when the
    command fails.
    """
    if not is_source_checkout():
        return None
    repo_root = _repo_root()
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


def parse_major_minor(text: str) -> tuple[int, int] | None:
    """Return `(major, minor)` of a version like `1.2.3`, `v1.2` or `1.2.3-volta`, or None if it has none."""
    match = re.match(r"v?(\d+)\.(\d+)(?![\d])", text)
    return (int(match[1]), int(match[2])) if match else None


def _is_compatible(cli: tuple[int, int] | None, tag: str) -> bool:
    """Return whether `tag` fits the already parsed CLI `cli` version, see `is_compatible_with_cli`."""
    component = parse_major_minor(tag)
    if cli is None or component is None:
        return True
    if cli[0] == 0:
        return component == cli
    return component[0] == cli[0] and component[1] <= cli[1]


def is_compatible_with_cli(tag: str) -> bool:
    """Return whether this CLI may install or update to a Server/Infra image `tag`.

    Only major and minor count, patch is ignored. From major 1 on, the component must share the CLI's
    major and must not be newer than the CLI's minor, so CLI 1.4 handles 1.0 to 1.4 but not 1.5 or 2.0.
    While the major is 0 a minor release may break compatibility, so the component must have exactly
    the CLI's minor: CLI 0.37 handles only 0.37.
    Anything that can't be compared (a dev build of the CLI, a tag such as `latest`) is allowed.
    """
    return _is_compatible(parse_major_minor(cli_version()), tag)


def compatible_tags(tags: list[str]) -> list[str]:
    """Return the `tags` this CLI may install, in their original order, resolving the CLI version once."""
    cli = parse_major_minor(cli_version())
    return [t for t in tags if _is_compatible(cli, t)]


def _service_version(service_dir: Path, image_key: str) -> str | None:
    """Return installed service version from its image tag in .env, or None if not installed."""
    if not service_dir.is_dir():
        return None
    image = read_env_file_to_dict(service_dir / ".env").get(image_key, "")
    if not isinstance(image, str) or ":" not in image:
        return "unknown"
    return image.rsplit(":", 1)[1].removeprefix("v")


def _running_service_version(service: str, service_dir: Path, configured: str) -> str:
    """Return the line to show for an installed service, saying where its version comes from.

    The version of the running container wins, as `.env` may point at an image that was pulled but never
    started. Otherwise the configured version is shown, with a note on why it is only that.

    Args:
        service: Compose service name, e.g. ``infra``.
        service_dir: Directory of the installation.
        configured: Version taken from the installation's `.env`.
    """
    try:
        running = is_service_running_or_raise(service, service_dir)
    except DockerError:
        return f"{configured} (from configuration, couldn't check whether it is running)"
    if not running:
        return f"{configured} (from configuration, stopped)"
    image = get_running_service_image(service, service_dir)
    tag = image.rpartition(":")[2].removeprefix("v") if image and ":" in image else None
    return f"{tag} (running)" if tag else f"{configured} (from configuration, running image has no version)"


def print_cli_version() -> None:
    """Show the DeepFellow CLI version only: no Docker calls, so it is fast enough for scripts."""
    print(f"DeepFellow CLI {cli_version()}")  # noqa: T201


def version() -> None:
    """Show the DeepFellow CLI version, and Infra and Server with the origin of theirs if installed."""
    from deepfellow.server.utils.options import get_default_server_directory

    print_cli_version()

    for name, service, directory, image_key in (
        ("Infra", "infra", DF_INFRA_DIRECTORY, "df_infra_image"),
        ("Server", "server", get_default_server_directory(), "df_server_image"),
    ):
        configured = _service_version(directory, image_key)
        if configured is not None:
            print(f"DeepFellow {name} {_running_service_version(service, directory, configured)}")  # noqa: T201
