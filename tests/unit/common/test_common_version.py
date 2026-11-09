# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import subprocess
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common import version as version_module
from deepfellow.common.docker import DockerError
from deepfellow.common.version import (
    _run_git,
    _running_service_version,
    _service_version,
    cli_version,
    is_compatible_with_cli,
    is_source_checkout,
    parse_major_minor,
    print_cli_version,
    version,
)


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@mock.patch("deepfellow.common.version.Path.exists", return_value=True)
def test_is_source_checkout_returns_true_when_git_dir_exists(mock_exists: Mock):
    result = is_source_checkout()

    assert result is True
    assert mock_exists.call_count == 1


@mock.patch("deepfellow.common.version.Path.exists", return_value=False)
def test_is_source_checkout_returns_false_when_git_dir_missing(mock_exists: Mock):
    result = is_source_checkout()

    assert result is False
    assert mock_exists.call_count == 1


@mock.patch("deepfellow.common.version.Path.exists", return_value=True)
@mock.patch("deepfellow.common.version.subprocess.run")
def test_run_git_returns_stripped_stdout(mock_run: Mock, mock_exists: Mock) -> None:
    mock_run.return_value = _completed(0, "v1.23\n")

    assert _run_git("describe", "--tags", "--exact-match") == "v1.23"
    assert mock_run.call_count == 1


@mock.patch("deepfellow.common.version.Path.exists", return_value=True)
@mock.patch("deepfellow.common.version.subprocess.run")
def test_run_git_returns_none_when_command_fails(mock_run: Mock, mock_exists: Mock) -> None:
    mock_run.return_value = _completed(128, "")

    assert _run_git("describe", "--tags", "--exact-match") is None


@mock.patch("deepfellow.common.version.Path.exists", return_value=False)
def test_run_git_returns_none_when_not_in_source_tree(mock_exists: Mock) -> None:
    # Installed package: no .git at the repo root, so git is never consulted.
    assert _run_git("rev-parse", "--short", "HEAD") is None


@mock.patch("deepfellow.common.version.Path.exists", return_value=True)
@mock.patch("deepfellow.common.version.subprocess.run")
def test_run_git_returns_none_when_git_missing(mock_run: Mock, mock_exists: Mock) -> None:
    mock_run.side_effect = OSError("git not found")

    assert _run_git("rev-parse", "--short", "HEAD") is None


@mock.patch("deepfellow.common.version._run_git")
def test_cli_version_prefers_tag_without_v_prefix(mock_run_git: Mock) -> None:
    mock_run_git.return_value = "v1.23"

    assert cli_version() == "1.23"
    assert mock_run_git.call_count == 1


@mock.patch("deepfellow.common.version._pkg_version")
@mock.patch("deepfellow.common.version._run_git")
def test_cli_version_falls_back_to_metadata_when_untagged(mock_run_git: Mock, mock_pkg_version: Mock) -> None:
    mock_run_git.return_value = None
    mock_pkg_version.return_value = "0.3.1"

    assert cli_version() == "0.3.1"


@mock.patch("deepfellow.common.version._pkg_version")
@mock.patch("deepfellow.common.version._run_git")
def test_cli_version_falls_back_to_commit_hash_when_no_version(mock_run_git: Mock, mock_pkg_version: Mock) -> None:
    mock_run_git.side_effect = [None, "abc1234"]  # no tag, then commit hash
    mock_pkg_version.side_effect = PackageNotFoundError("deepfellow-cli")

    assert cli_version() == "abc1234"
    assert mock_run_git.call_count == 2


@mock.patch("deepfellow.common.version._pkg_version")
@mock.patch("deepfellow.common.version._run_git")
def test_cli_version_unknown_when_nothing_available(mock_run_git: Mock, mock_pkg_version: Mock) -> None:
    mock_run_git.return_value = None
    mock_pkg_version.side_effect = PackageNotFoundError("deepfellow-cli")

    assert cli_version() == "unknown"


@mock.patch("deepfellow.common.version.Path.is_dir")
def test_service_version_returns_none_when_not_installed(mock_is_dir: Mock) -> None:
    mock_is_dir.return_value = False

    assert _service_version(Path("/missing"), "df_infra_image") is None


@mock.patch("deepfellow.common.version.read_env_file_to_dict")
@mock.patch("deepfellow.common.version.Path.is_dir")
def test_service_version_returns_image_tag(mock_is_dir: Mock, mock_read: Mock) -> None:
    mock_is_dir.return_value = True
    mock_read.return_value = {"df_infra_image": "hub.simplito.com/df/infra:4.56"}

    assert _service_version(Path("/infra"), "df_infra_image") == "4.56"


@mock.patch("deepfellow.common.version.read_env_file_to_dict")
@mock.patch("deepfellow.common.version.Path.is_dir")
def test_service_version_strips_v_prefix_from_tag(mock_is_dir: Mock, mock_read: Mock) -> None:
    mock_is_dir.return_value = True
    mock_read.return_value = {"df_infra_image": "hub.simplito.com/df/infra:v0.29.0"}

    assert _service_version(Path("/infra"), "df_infra_image") == "0.29.0"


@mock.patch("deepfellow.common.version.read_env_file_to_dict")
@mock.patch("deepfellow.common.version.Path.is_dir")
def test_service_version_unknown_when_image_has_no_tag(mock_is_dir: Mock, mock_read: Mock) -> None:
    mock_is_dir.return_value = True
    mock_read.return_value = {"df_infra_image": "hub.simplito.com/df/infra"}

    assert _service_version(Path("/infra"), "df_infra_image") == "unknown"


@mock.patch("deepfellow.common.version.cli_version", return_value="1.23")
def test_print_cli_version_prints_only_cli_version(mock_cli_version: Mock, capsys: pytest.CaptureFixture[str]) -> None:
    print_cli_version()

    assert capsys.readouterr().out == "DeepFellow CLI 1.23\n"


@mock.patch("deepfellow.server.utils.options.get_default_server_directory")
@mock.patch("deepfellow.common.version._service_version", return_value=None)
@mock.patch("deepfellow.common.version.cli_version", return_value="1.23")
def test_version_prints_cli_only_when_nothing_installed(
    mock_cli_version: Mock, mock_service_version: Mock, mock_server_dir: Mock, capsys: pytest.CaptureFixture[str]
) -> None:
    version()

    assert capsys.readouterr().out == "DeepFellow CLI 1.23\n"


@mock.patch("deepfellow.common.version.get_running_service_image")
@mock.patch("deepfellow.common.version.is_service_running_or_raise", return_value=True)
@mock.patch("deepfellow.server.utils.options.get_default_server_directory")
@mock.patch("deepfellow.common.version._service_version")
@mock.patch("deepfellow.common.version.cli_version", return_value="1.23")
def test_version_prints_running_versions_from_containers_in_default_directories(
    mock_cli_version: Mock,
    mock_service_version: Mock,
    mock_server_dir: Mock,
    mock_is_running: Mock,
    mock_running_image: Mock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    mock_service_version.side_effect = ["4.56", "7.89"]
    mock_server_dir.return_value = Path("/custom/server")
    mock_running_image.side_effect = ["hub/infra:v4.57.0", "hub/server:7.90.1"]

    version()

    assert (
        capsys.readouterr().out
        == "DeepFellow CLI 1.23\nDeepFellow Infra 4.57.0 (running)\nDeepFellow Server 7.90.1 (running)\n"
    )
    assert mock_service_version.call_args_list == [
        mock.call(version_module.DF_INFRA_DIRECTORY, "df_infra_image"),
        mock.call(Path("/custom/server"), "df_server_image"),
    ]
    assert mock_is_running.call_args_list == [
        mock.call("infra", version_module.DF_INFRA_DIRECTORY),
        mock.call("server", Path("/custom/server")),
    ]


@mock.patch("deepfellow.common.version.get_running_service_image")
@mock.patch("deepfellow.common.version.is_service_running_or_raise", return_value=False)
def test_running_service_version_reports_configured_version_when_stack_stopped(
    mock_is_running: Mock, mock_running_image: Mock
) -> None:
    result = _running_service_version("infra", Path("/infra"), "4.56")

    assert result == "4.56 (from configuration, stopped)"
    assert mock_running_image.call_count == 0


@mock.patch("deepfellow.common.version.get_running_service_image")
@mock.patch("deepfellow.common.version.is_service_running_or_raise", side_effect=DockerError("daemon down"))
def test_running_service_version_reports_configured_version_when_docker_cannot_be_checked(
    mock_is_running: Mock, mock_running_image: Mock
) -> None:
    result = _running_service_version("infra", Path("/infra"), "4.56")

    assert result == "4.56 (from configuration, couldn't check whether it is running)"
    assert mock_running_image.call_count == 0


@pytest.mark.parametrize("running_image", [pytest.param(None, id="no-image"), pytest.param("hub/infra", id="no-tag")])
@mock.patch("deepfellow.common.version.get_running_service_image")
@mock.patch("deepfellow.common.version.is_service_running_or_raise", return_value=True)
def test_running_service_version_falls_back_to_configuration_when_running_image_has_no_version(
    mock_is_running: Mock, mock_running_image: Mock, running_image: str | None
) -> None:
    mock_running_image.return_value = running_image

    result = _running_service_version("infra", Path("/infra"), "4.56")

    assert result == "4.56 (from configuration, running image has no version)"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("1.2.3", (1, 2), id="full-version"),
        pytest.param("v1.2", (1, 2), id="v-prefix-no-patch"),
        pytest.param("1.2.3-volta", (1, 2), id="suffix"),
        pytest.param("0.37.0", (0, 37), id="zero-major"),
        pytest.param("latest", None, id="non-version"),
        pytest.param("1", None, id="major-only"),
        pytest.param("", None, id="empty"),
    ],
)
def test_parse_major_minor_extracts_major_and_minor(text: str, expected: tuple[int, int] | None) -> None:
    result = parse_major_minor(text)

    assert result == expected


@pytest.mark.parametrize(
    ("cli", "tag", "expected"),
    [
        pytest.param("1.4.2", "1.4.9", True, id="same-minor-newer-patch"),
        pytest.param("1.4.2", "v1.2.0", True, id="older-minor-v-prefix"),
        pytest.param("1.4.2", "1.5.0", False, id="newer-minor"),
        pytest.param("1.4.2", "2.0.0", False, id="newer-major"),
        pytest.param("1.4.2", "0.9.0", False, id="older-major"),
        pytest.param("1.4.2", "latest", True, id="non-version-tag"),
        pytest.param("abc1234", "2.0.0", True, id="dev-cli"),
        pytest.param("0.37.0", "0.37.5", True, id="zero-major-same-minor"),
        pytest.param("0.37.0", "v0.37.0", True, id="zero-major-v-prefix"),
        pytest.param("0.37.0", "0.36.9", False, id="zero-major-older-minor"),
        pytest.param("0.37.0", "0.38.0", False, id="zero-major-newer-minor"),
        pytest.param("0.37.0", "1.0.0", False, id="zero-major-newer-major"),
    ],
)
@mock.patch("deepfellow.common.version.cli_version")
def test_is_compatible_with_cli_compares_major_and_minor(
    mock_cli_version: Mock, cli: str, tag: str, expected: bool
) -> None:
    mock_cli_version.return_value = cli

    result = is_compatible_with_cli(tag)

    assert result is expected
