# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock
from unittest.mock import Mock

from deepfellow.common import version as version_module
from deepfellow.common.version import _run_git, _service_version, cli_version, version


def _completed(returncode: int, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


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


@mock.patch("deepfellow.common.version._service_version")
@mock.patch("deepfellow.common.version.cli_version")
def test_version_prints_cli_only_when_nothing_installed(
    mock_cli_version: Mock, mock_service_version: Mock, capsys
) -> None:
    mock_cli_version.return_value = "1.23"
    mock_service_version.return_value = None

    version()

    out = capsys.readouterr().out
    assert out == "DeepFellow CLI 1.23\n"


@mock.patch("deepfellow.common.version._service_version")
@mock.patch("deepfellow.common.version.cli_version")
def test_version_prints_all_when_both_installed(mock_cli_version: Mock, mock_service_version: Mock, capsys) -> None:
    mock_cli_version.return_value = "1.23"
    mock_service_version.side_effect = ["4.56", "7.89"]

    version()

    out = capsys.readouterr().out
    assert out == "DeepFellow CLI 1.23\nDeepFellow Infra 4.56\nDeepFellow Server 7.89\n"
    assert mock_service_version.call_count == 2
    assert mock_service_version.call_args_list == [
        mock.call(version_module.DF_INFRA_DIRECTORY, "df_infra_image"),
        mock.call(version_module.DF_SERVER_DIRECTORY, "df_server_image"),
    ]
