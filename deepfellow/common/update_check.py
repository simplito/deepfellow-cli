# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Startup notice about a newer DeepFellow CLI release."""

import os
import re
import time
from typing import Any

import httpx

from deepfellow.common.config import save_env_file
from deepfellow.common.defaults import (
    DF_CLI_LATEST_PYPROJECT_URL,
    DF_NO_UPDATE_CHECK_ENV,
    DF_UPDATE_CHECK_INTERVAL_SECONDS,
    DF_UPDATE_CHECK_TIMEOUT_SECONDS,
)
from deepfellow.common.echo import echo, echo_err
from deepfellow.common.state import state
from deepfellow.common.version import cli_version, is_source_checkout

LAST_CHECKED_KEY = "DF_UPDATE_CHECK__LAST_CHECKED"
LATEST_VERSION_KEY = "DF_UPDATE_CHECK__LATEST_VERSION"
# Where `main()` puts the two keys above in `state.cli_config` (`env_to_dict` keeps the `DF_` prefix).
CACHE_KEY = "df_update_check"

NOTICE = (
    "A new DeepFellow CLI version is available: {installed} → {latest}. "
    "Run `deepfellow cli update` to upgrade the CLI (or `deepfellow update` to also update Infra and Server)."
)

# Body of the [project] table: from its header up to the next table header (or end of file).
_PROJECT_TABLE_RE = re.compile(r"^\[project\][ \t]*$(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
_VERSION_LINE_RE = re.compile(r'^version\s*=\s*"([^"]+)"\s*(?:#.*)?$', re.MULTILINE)
_RELEASE_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def _latest_from_pyproject(text: str) -> str | None:
    """Return the `version` of the `[project]` table in pyproject.toml content, or None if absent."""
    table = _PROJECT_TABLE_RE.search(text)
    if table is None:
        return None
    version_line = _VERSION_LINE_RE.search(table.group(1))
    return version_line.group(1) if version_line else None


def _parse_version(text: str) -> tuple[int, int, int] | None:
    """Parse an `X.Y.Z` release version (optional leading `v`); None for anything else."""
    match = _RELEASE_RE.fullmatch(text.strip())
    if match is None:
        return None
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def _fetch_latest_version() -> str | None:
    """Fetch the latest released CLI version from GitHub; None on any failure."""
    try:
        response = httpx.get(
            DF_CLI_LATEST_PYPROJECT_URL, timeout=DF_UPDATE_CHECK_TIMEOUT_SECONDS, follow_redirects=True
        )
    except httpx.HTTPError as exc:
        echo.debug(f"Update check failed: {exc!r}")
        return None

    if response.status_code != httpx.codes.OK:
        echo.debug(f"Update check failed: HTTP {response.status_code} from {DF_CLI_LATEST_PYPROJECT_URL}")
        return None

    latest = _latest_from_pyproject(response.text)
    # Validated before it is cached, so a pre-release on main can't replace a good stored version.
    if latest is None or _parse_version(latest) is None:
        echo.debug(f"Update check failed: no X.Y.Z [project] version in {DF_CLI_LATEST_PYPROJECT_URL} ({latest!r})")
        return None
    return latest


def _load_cache() -> tuple[int | None, str | None]:
    """Return the stored (last check time, latest version).

    The time is None when missing, invalid or in the future (e.g. the clock was set back),
    so the caller treats it as no previous check.
    """
    cache = state.cli_config.get(CACHE_KEY)
    if not isinstance(cache, dict):
        return None, None

    last_checked = cache.get("last_checked")
    # bool is an int subclass: a "true"/"false" value is not a timestamp.
    if not isinstance(last_checked, int) or isinstance(last_checked, bool) or last_checked > time.time():
        last_checked = None

    latest = cache.get("latest_version")
    return last_checked, latest if isinstance(latest, str) else None


def _save_cache(checked_at: int, latest: str | None) -> None:
    """Store the check time, and the latest version when known, in the CLI config.

    A None `latest` (failed check) leaves the previously stored version in place.
    """
    values = {LAST_CHECKED_KEY: str(checked_at)}
    cache: dict[str, Any] = {"last_checked": checked_at}
    if latest is not None:
        values[LATEST_VERSION_KEY] = latest
        cache["latest_version"] = latest

    previous = state.cli_config.get(CACHE_KEY)
    state.cli_config[CACHE_KEY] = {**previous, **cache} if isinstance(previous, dict) else cache

    try:
        save_env_file(state.cli_config_file, values, docker_note=False, quiet=True)
    except OSError as exc:
        echo.debug(f"Could not save the update check result to {state.cli_config_file.as_posix()}: {exc!r}")


def _should_skip() -> bool:
    """Return whether the check is disabled for this run, regardless of the command."""
    return os.environ.get(DF_NO_UPDATE_CHECK_ENV) == "1" or state.non_interactive or is_source_checkout()


def _check_for_update() -> None:
    if _should_skip():
        return

    now = int(time.time())
    last_checked, latest = _load_cache()
    if last_checked is None or now - last_checked >= DF_UPDATE_CHECK_INTERVAL_SECONDS:
        fetched = _fetch_latest_version()
        _save_cache(now, fetched)
        latest = fetched or latest

    installed = cli_version()
    installed_release = _parse_version(installed)
    if installed_release is None:
        echo.debug(f"Update check skipped: installed version {installed!r} is not X.Y.Z")
        return

    latest_release = _parse_version(latest) if latest else None
    if latest_release is None or latest_release <= installed_release:
        return

    echo_err.warning(NOTICE.format(installed=installed, latest=latest))


def check_for_update() -> None:
    """Warn on stderr when a newer DeepFellow CLI release is available.

    Contacts GitHub at most once per `DF_UPDATE_CHECK_INTERVAL_SECONDS` and otherwise decides from
    the result stored in the CLI config. Skipped with `--non-interactive`, from a source
    checkout, or when `DF_NO_UPDATE_CHECK=1` is set. Never raises.
    """
    try:
        _check_for_update()
    except Exception as exc:  # The check must never break the command it runs before.
        echo.debug(f"Update check failed: {exc!r}")
