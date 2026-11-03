# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from typing import Any
from unittest import mock
from unittest.mock import Mock

import httpx
import pytest

from deepfellow.common.config import env_to_dict
from deepfellow.common.defaults import (
    DF_CLI_LATEST_PYPROJECT_URL,
    DF_NO_UPDATE_CHECK_ENV,
    DF_UPDATE_CHECK_INTERVAL_SECONDS,
)
from deepfellow.common.state import state
from deepfellow.common.update_check import (
    CACHE_KEY,
    LAST_CHECKED_KEY,
    LATEST_VERSION_KEY,
    _fetch_latest_version,
    _latest_from_pyproject,
    _load_cache,
    _parse_version,
    _save_cache,
    check_for_update,
)

_MODULE = "deepfellow.common.update_check"
NOW = 1_800_000_000
PYPROJECT = '[project]\nname = "deepfellow-cli"\nversion = "0.38.0"\n\n[project.scripts]\ndeepfellow = "x:app"\n'
NOTICE = (
    "A new DeepFellow CLI version is available: 0.37.0 → 0.38.0. "
    "Run `deepfellow cli update` to upgrade the CLI (or `deepfellow update` to also update Infra and Server)."
)


def _fresh_cache(latest: str) -> dict[str, Any]:
    return {CACHE_KEY: {"last_checked": NOW - 60, "latest_version": latest}}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (PYPROJECT, "0.38.0"),
        ('[project]\nname = "x"\nversion = "0.38.0"  # bumped on release\n', "0.38.0"),
        ('[project]\nname = "x"\n\n[tool.other]\nversion = "9.9.9"\n', None),
        ('[project]\nname = "x"\n', None),
        ('[tool.other]\nversion = "9.9.9"\n', None),
    ],
)
def test_latest_from_pyproject_returns_project_version(text: str, expected: str | None):
    result = _latest_from_pyproject(text)

    assert result == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("0.37.0", (0, 37, 0)),
        ("v1.2.3", (1, 2, 3)),
    ],
)
def test_parse_version_returns_release_tuple(text: str, expected: tuple[int, int, int]):
    result = _parse_version(text)

    assert result == expected


@pytest.mark.parametrize("text", ["a1b2c3d", "unknown", "0.38.0rc1", ""])
def test_parse_version_returns_none_for_non_release(text: str):
    result = _parse_version(text)

    assert result is None


@mock.patch(f"{_MODULE}.httpx.get")
def test_fetch_latest_version_returns_version_on_success(mock_get: Mock):
    mock_get.return_value = httpx.Response(200, text=PYPROJECT)

    result = _fetch_latest_version()

    assert result == "0.38.0"
    assert mock_get.call_count == 1
    assert mock_get.call_args == mock.call(DF_CLI_LATEST_PYPROJECT_URL, timeout=2.0, follow_redirects=True)


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.httpx.get")
def test_fetch_latest_version_returns_none_on_http_error_status(mock_get: Mock, mock_echo: Mock):
    mock_get.return_value = httpx.Response(404, text="Not Found")

    result = _fetch_latest_version()

    assert result is None
    assert mock_echo.debug.call_count == 1


@pytest.mark.parametrize("text", ["<html>captive portal</html>", '[project]\nversion = "1.4.0rc1"\n'])
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.httpx.get")
def test_fetch_latest_version_returns_none_when_no_release_version(mock_get: Mock, mock_echo: Mock, text: str):
    mock_get.return_value = httpx.Response(200, text=text)

    result = _fetch_latest_version()

    assert result is None
    assert mock_echo.debug.call_count == 1


@pytest.mark.parametrize("error", [httpx.TimeoutException("timed out"), httpx.ConnectError("refused")])
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.httpx.get")
def test_fetch_latest_version_returns_none_on_network_error(mock_get: Mock, mock_echo: Mock, error: httpx.HTTPError):
    mock_get.side_effect = error

    result = _fetch_latest_version()

    assert result is None
    assert mock_echo.debug.call_count == 1


@mock.patch.object(state, "cli_config", {})
def test_load_cache_returns_none_when_missing():
    result = _load_cache()

    assert result == (None, None)


@mock.patch.object(state, "cli_config", {CACHE_KEY: "not-a-table"})
def test_load_cache_returns_none_when_cache_is_not_a_table():
    result = _load_cache()

    assert result == (None, None)


@mock.patch(f"{_MODULE}.time")
def test_load_cache_returns_stored_values(mock_time: Mock):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    result = _load_cache()

    assert result == (NOW - 60, "0.38.0")


@mock.patch(f"{_MODULE}.time")
def test_load_cache_reads_keys_parsed_from_config_file(mock_time: Mock):
    mock_time.time.return_value = NOW
    state.cli_config = env_to_dict({LAST_CHECKED_KEY: str(NOW - 60), LATEST_VERSION_KEY: "0.38.0"})

    result = _load_cache()

    assert result == (NOW - 60, "0.38.0")


@pytest.mark.parametrize("last_checked", ["yesterday", True, NOW + 60])
@mock.patch(f"{_MODULE}.time")
def test_load_cache_treats_timestamp_as_stale(mock_time: Mock, last_checked: object):
    mock_time.time.return_value = NOW
    state.cli_config = {CACHE_KEY: {"last_checked": last_checked, "latest_version": "0.38.0"}}

    result = _load_cache()

    assert result == (None, "0.38.0")


@mock.patch(f"{_MODULE}.time")
def test_load_cache_ignores_non_string_version(mock_time: Mock):
    mock_time.time.return_value = NOW
    state.cli_config = {CACHE_KEY: {"last_checked": NOW - 60, "latest_version": 38}}

    result = _load_cache()

    assert result == (NOW - 60, None)


@mock.patch(f"{_MODULE}.save_env_file")
def test_save_cache_writes_both_keys(mock_save_env_file: Mock):
    state.cli_config = {}

    _save_cache(NOW, "0.38.0")

    assert mock_save_env_file.call_count == 1
    assert mock_save_env_file.call_args == mock.call(
        state.cli_config_file,
        {LAST_CHECKED_KEY: str(NOW), LATEST_VERSION_KEY: "0.38.0"},
        docker_note=False,
        quiet=True,
    )
    assert state.cli_config[CACHE_KEY] == {"last_checked": NOW, "latest_version": "0.38.0"}


@mock.patch(f"{_MODULE}.save_env_file")
def test_save_cache_writes_only_timestamp_after_failed_fetch(mock_save_env_file: Mock):
    state.cli_config = {CACHE_KEY: {"last_checked": 1, "latest_version": "0.36.0"}}

    _save_cache(NOW, None)

    assert mock_save_env_file.call_args == mock.call(
        state.cli_config_file, {LAST_CHECKED_KEY: str(NOW)}, docker_note=False, quiet=True
    )
    assert state.cli_config[CACHE_KEY] == {"last_checked": NOW, "latest_version": "0.36.0"}


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.save_env_file")
def test_save_cache_ignores_os_error(mock_save_env_file: Mock, mock_echo: Mock):
    mock_save_env_file.side_effect = OSError("read-only file system")
    state.cli_config = {}

    _save_cache(NOW, "0.38.0")

    assert mock_echo.debug.call_count == 1
    assert state.cli_config[CACHE_KEY] == {"last_checked": NOW, "latest_version": "0.38.0"}


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_warns_from_fresh_cache_without_fetch(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_fetch_latest_version.call_count == 0
    assert mock_save_env_file.call_count == 0
    assert mock_echo_err.warning.call_count == 1
    assert mock_echo_err.warning.call_args == mock.call(NOTICE)


@pytest.mark.parametrize(
    ("latest", "installed"),
    [
        ("0.37.0", "0.37.0"),
        ("0.36.0", "0.37.0"),
        ("0.38.0", "a1b2c3d"),
    ],
)
@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_stays_silent_when_not_newer(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
    latest: str,
    installed: str,
):
    mock_cli_version.return_value = installed
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache(latest)

    check_for_update()

    assert mock_echo_err.warning.call_count == 0


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.9.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_compares_versions_numerically(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.10.0")

    check_for_update()

    assert mock_echo_err.warning.call_count == 1


@pytest.mark.parametrize(
    "cli_config",
    [
        {},
        {CACHE_KEY: {"last_checked": NOW - DF_UPDATE_CHECK_INTERVAL_SECONDS, "latest_version": "0.36.0"}},
        {CACHE_KEY: {"last_checked": NOW + 60, "latest_version": "0.36.0"}},
    ],
)
@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version", return_value="0.38.0")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_fetches_and_saves_when_cache_stale(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
    cli_config: dict[str, Any],
):
    mock_time.time.return_value = NOW
    state.cli_config = cli_config

    check_for_update()

    assert mock_fetch_latest_version.call_count == 1
    assert mock_save_env_file.call_args == mock.call(
        state.cli_config_file,
        {LAST_CHECKED_KEY: str(NOW), LATEST_VERSION_KEY: "0.38.0"},
        docker_note=False,
        quiet=True,
    )
    assert mock_echo_err.warning.call_args == mock.call(NOTICE)


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version", return_value=None)
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_saves_timestamp_and_stays_silent_on_fetch_failure(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = {}

    check_for_update()

    assert mock_save_env_file.call_args == mock.call(
        state.cli_config_file, {LAST_CHECKED_KEY: str(NOW)}, docker_note=False, quiet=True
    )
    assert mock_echo_err.warning.call_count == 0


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "1"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_skips_when_env_var_set(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_fetch_latest_version.call_count == 0
    assert mock_save_env_file.call_count == 0
    assert mock_echo_err.warning.call_count == 0


@mock.patch.object(state, "non_interactive", True)
@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_skips_in_non_interactive_mode(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_fetch_latest_version.call_count == 0
    assert mock_save_env_file.call_count == 0
    assert mock_echo_err.warning.call_count == 0


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=True)
def test_check_for_update_skips_in_source_checkout(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_fetch_latest_version.call_count == 0
    assert mock_save_env_file.call_count == 0
    assert mock_echo_err.warning.call_count == 0


@mock.patch.object(state, "yes", True)
@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_runs_with_yes_flag(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_echo_err.warning.call_args == mock.call(NOTICE)


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_swallows_unexpected_error(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_fetch_latest_version.side_effect = RuntimeError("boom")
    mock_time.time.return_value = NOW
    state.cli_config = {}

    check_for_update()

    assert mock_echo.debug.call_count == 1
    assert mock_echo_err.warning.call_count == 0


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version", return_value=None)
@mock.patch(f"{_MODULE}.cli_version", return_value="0.37.0")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_warns_from_stale_cache_when_fetch_fails(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = {CACHE_KEY: {"last_checked": NOW - DF_UPDATE_CHECK_INTERVAL_SECONDS, "latest_version": "0.38.0"}}

    check_for_update()

    assert mock_fetch_latest_version.call_count == 1
    assert mock_save_env_file.call_args == mock.call(
        state.cli_config_file, {LAST_CHECKED_KEY: str(NOW)}, docker_note=False, quiet=True
    )
    assert mock_echo_err.warning.call_args == mock.call(NOTICE)


@mock.patch.dict("os.environ", {DF_NO_UPDATE_CHECK_ENV: "0"})
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.echo_err")
@mock.patch(f"{_MODULE}.save_env_file")
@mock.patch(f"{_MODULE}.time")
@mock.patch(f"{_MODULE}._fetch_latest_version")
@mock.patch(f"{_MODULE}.cli_version", return_value="a1b2c3d")
@mock.patch(f"{_MODULE}.is_source_checkout", return_value=False)
def test_check_for_update_logs_debug_for_non_release_installed_version(
    mock_is_source_checkout: Mock,
    mock_cli_version: Mock,
    mock_fetch_latest_version: Mock,
    mock_time: Mock,
    mock_save_env_file: Mock,
    mock_echo_err: Mock,
    mock_echo: Mock,
):
    mock_time.time.return_value = NOW
    state.cli_config = _fresh_cache("0.38.0")

    check_for_update()

    assert mock_echo.debug.call_count == 1
    assert mock_echo_err.warning.call_count == 0
