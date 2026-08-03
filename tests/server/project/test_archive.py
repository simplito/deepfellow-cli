# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.server.project.archive import archive
from deepfellow.server.project.utils import Project


@pytest.fixture
def project() -> Project:
    return Project(
        name="Acme",
        id="project-id",
        status="archived",
        models=["model-a"],
        custom_endpoints=[],
        mcp_prefixes=[],
        created_at=0.0,
    )


@mock.patch("deepfellow.server.project.archive.state")
@mock.patch("deepfellow.server.project.archive.echo.debug")
@mock.patch("deepfellow.server.project.archive.echo.info")
@mock.patch("deepfellow.server.project.archive.echo.confirm")
@mock.patch("deepfellow.server.project.archive.archive_project")
@mock.patch("deepfellow.server.project.archive.get_token")
@mock.patch("deepfellow.server.project.archive.get_server_url")
def test_archive_calls_archive_project_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_archive_project: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    project: Project,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_confirm.return_value = True
    mock_archive_project.return_value = project

    archive(server=None, organization_id="org-id", project_id="project-id")

    assert mock_archive_project.call_count == 1
    assert mock_archive_project.call_args == mock.call("https://server", "token", "org-id", "project-id")
    assert mock_info.call_args == mock.call(str(project))


@mock.patch("deepfellow.server.project.archive.state")
@mock.patch("deepfellow.server.project.archive.echo.debug")
@mock.patch("deepfellow.server.project.archive.echo.info")
@mock.patch("deepfellow.server.project.archive.echo.confirm")
@mock.patch("deepfellow.server.project.archive.archive_project")
@mock.patch("deepfellow.server.project.archive.get_token")
@mock.patch("deepfellow.server.project.archive.get_server_url")
def test_archive_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_archive_project: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
) -> None:
    mock_state.yes = False
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        archive(server=None, organization_id="org-id", project_id="project-id")

    assert exc_info.value.exit_code == 1
    assert mock_archive_project.call_count == 0


@mock.patch("deepfellow.server.project.archive.state")
@mock.patch("deepfellow.server.project.archive.echo.debug")
@mock.patch("deepfellow.server.project.archive.echo.info")
@mock.patch("deepfellow.server.project.archive.echo.confirm")
@mock.patch("deepfellow.server.project.archive.archive_project")
@mock.patch("deepfellow.server.project.archive.get_token")
@mock.patch("deepfellow.server.project.archive.get_server_url")
def test_archive_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_archive_project: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    project: Project,
) -> None:
    mock_state.yes = True
    mock_archive_project.return_value = project

    archive(server=None, organization_id="org-id", project_id="project-id")

    assert mock_confirm.call_count == 0
    assert mock_archive_project.call_count == 1
    assert mock_info.call_args == mock.call(str(project))


@mock.patch("deepfellow.server.project.archive.state")
@mock.patch("deepfellow.server.project.archive.echo.debug")
@mock.patch("deepfellow.server.project.archive.echo.info")
@mock.patch("deepfellow.server.project.archive.echo.confirm")
@mock.patch("deepfellow.server.project.archive.archive_project")
@mock.patch("deepfellow.server.project.archive.get_token")
@mock.patch("deepfellow.server.project.archive.get_server_url")
def test_archive_logs_debug_message_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_archive_project: Mock,
    mock_confirm: Mock,
    mock_info: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    project: Project,
) -> None:
    mock_state.yes = True
    mock_archive_project.return_value = project

    archive(server=None, organization_id="org-id", project_id="project-id")

    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the archive.")
