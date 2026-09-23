# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the suite install state module."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.suite.utils.state import SuiteInstallState, delete, load, save


def test_load_returns_none_when_file_missing(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"

    result = load(state_file)

    assert result is None


@mock.patch("deepfellow.suite.utils.state.echo")
def test_load_returns_none_when_file_missing_does_not_warn(mock_echo: Mock, tmp_path: Path) -> None:
    """A missing file is the normal "nothing to resume" case (e.g. a first-ever run) - unlike a
    file that exists but can't be read, it isn't worth warning about."""
    state_file = tmp_path / "suite_install_state.json"

    load(state_file)

    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.suite.utils.state.echo")
def test_load_returns_none_and_warns_for_invalid_json(mock_echo: Mock, tmp_path: Path) -> None:
    """A file that exists but can't be parsed (e.g. corrupted by a crash mid-write) must warn -
    load() is always called at the start of install(), regardless of --resume, so silently
    treating this as "nothing to resume" would leave no indication anything was wrong."""
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text("not valid json", encoding="utf-8")

    result = load(state_file)

    assert result is None
    assert mock_echo.warning.call_count == 1
    assert str(state_file) in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.suite.utils.state.echo")
def test_load_returns_none_and_warns_for_non_dict_json(mock_echo: Mock, tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text("[1, 2, 3]", encoding="utf-8")

    result = load(state_file)

    assert result is None
    assert mock_echo.warning.call_count == 1


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    install_state = SuiteInstallState(
        completed_steps=["infra_install", "infra_start"],
        workspace={"organization": {"id": "org-1"}},
    )

    save(install_state, state_file)
    result = load(state_file)

    assert result == install_state


def test_save_then_load_round_trips_admin(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    install_state = SuiteInstallState(
        completed_steps=["infra_install"],
        admin={"name": "Admin", "email": "admin@example.com", "password": "Sup3r$ecret!"},
    )

    save(install_state, state_file)
    result = load(state_file)

    assert result == install_state


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    state_file = tmp_path / "nested" / "suite_install_state.json"

    save(SuiteInstallState(), state_file)

    assert state_file.is_file()


def test_save_overwrites_previous_content(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    save(SuiteInstallState(completed_steps=["infra_install"]), state_file)

    save(SuiteInstallState(completed_steps=["infra_install", "infra_start"]), state_file)
    result = load(state_file)

    assert result is not None
    assert result.completed_steps == ["infra_install", "infra_start"]


def test_save_writes_via_a_temp_file_not_the_target_directly(tmp_path: Path) -> None:
    """save() must never write into state_file directly - only os.replace() the finished temp
    file into place - so a crash mid-write can never leave a truncated, half-written state_file
    behind; at most it leaves an orphaned, harmless temp file next to it."""
    state_file = tmp_path / "suite_install_state.json"

    save(SuiteInstallState(completed_steps=["infra_install"]), state_file)

    assert list(tmp_path.iterdir()) == [state_file]


@mock.patch("deepfellow.suite.utils.state.Path.replace")
def test_save_cleans_up_temp_file_when_replace_fails(mock_replace: Mock, tmp_path: Path) -> None:
    """A failure during the atomic swap itself (e.g. a permissions/disk error) must not leave an
    orphaned temp file behind on every failed attempt."""
    mock_replace.side_effect = OSError("disk full")
    state_file = tmp_path / "suite_install_state.json"

    with pytest.raises(OSError, match="disk full"):
        save(SuiteInstallState(completed_steps=["infra_install"]), state_file)

    assert list(tmp_path.iterdir()) == []


def test_delete_removes_existing_file(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    save(SuiteInstallState(), state_file)

    delete(state_file)

    assert not state_file.exists()


def test_delete_is_a_no_op_when_file_missing(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"

    delete(state_file)

    assert not state_file.exists()


def test_load_defaults_completed_steps_when_explicitly_null(tmp_path: Path) -> None:
    """`{"completed_steps": null}` (as opposed to the key being absent) makes dict.get() return
    None rather than its default, and list(None) raises TypeError - load() must still default to
    an empty list rather than crashing."""
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text('{"completed_steps": null}', encoding="utf-8")

    result = load(state_file)

    assert result is not None
    assert result.completed_steps == []


def test_load_defaults_workspace_and_admin_when_absent(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text('{"completed_steps": ["infra_install"]}', encoding="utf-8")

    result = load(state_file)

    assert result is not None
    assert result.completed_steps == ["infra_install"]
    assert result.workspace is None
    assert result.admin is None
    assert result.completed_steps == ["infra_install"]


def test_load_defaults_infra_and_server_config_when_absent(tmp_path: Path) -> None:
    """A state file written before infra_config/server_config existed (or a fresh install that
    hasn't reached those steps yet) must default both to None, not raise."""
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text('{"completed_steps": ["infra_install"]}', encoding="utf-8")

    result = load(state_file)

    assert result is not None
    assert result.infra_config is None
    assert result.server_config is None


def test_save_then_load_round_trips_infra_and_server_config(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    install_state = SuiteInstallState(
        completed_steps=["infra_config", "server_config"],
        infra_config={"df_name": "deepfellow", "api_key": "infra-api-key"},
        server_config={"port": 8080, "otel": {"envs": {}, "docker_compose": {}}},
    )

    save(install_state, state_file)
    result = load(state_file)

    assert result == install_state


def test_load_defaults_template_when_absent(tmp_path: Path) -> None:
    """A state file written before `template` existed must default it to None, not raise - the
    same one-time fallback every other field above gets."""
    state_file = tmp_path / "suite_install_state.json"
    state_file.write_text('{"completed_steps": ["infra_install"]}', encoding="utf-8")

    result = load(state_file)

    assert result is not None
    assert result.template is None


def test_save_then_load_round_trips_template(tmp_path: Path) -> None:
    state_file = tmp_path / "suite_install_state.json"
    install_state = SuiteInstallState(completed_steps=["infra_config"], template="workspace")

    save(install_state, state_file)
    result = load(state_file)

    assert result == install_state
