# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.server.project.get import get
from deepfellow.server.project.utils import Project


@pytest.fixture
def project() -> Project:
    return Project(
        name="Acme",
        id="project-id",
        status="active",
        models=["model-a"],
        custom_endpoints=[],
        mcp_prefixes=[],
        created_at=0.0,
    )


@mock.patch("deepfellow.server.project.get.state")
@mock.patch("deepfellow.server.project.get.echo.info")
@mock.patch("deepfellow.server.project.get.get_project")
@mock.patch("deepfellow.server.project.get.get_token")
@mock.patch("deepfellow.server.project.get.get_server_url")
def test_get_prints_project_returned_by_get_project(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_info: Mock,
    mock_state: Mock,
    project: Project,
) -> None:
    mock_state.cli_secrets_file = Path("/secrets")
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = project

    get(server=None, organization_id="org-id", project_id="project-id")

    assert mock_get_project.call_count == 1
    assert mock_get_project.call_args == mock.call("https://server", "token", "org-id", "project-id")
    assert mock_info.call_args == mock.call(str(project))


@mock.patch("deepfellow.server.project.get.state")
@mock.patch("deepfellow.server.project.get.echo.info")
@mock.patch("deepfellow.server.project.get.get_project")
@mock.patch("deepfellow.server.project.get.get_token")
@mock.patch("deepfellow.server.project.get.get_server_url")
def test_get_resolves_token_using_server_url_and_secrets_file(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_info: Mock,
    mock_state: Mock,
    project: Project,
) -> None:
    mock_state.cli_secrets_file = Path("/secrets")
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = project

    get(server="https://server", organization_id="org-id", project_id="project-id")

    assert mock_get_server_url.call_count == 1
    assert mock_get_server_url.call_args == mock.call("https://server")
    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call(Path("/secrets"), "https://server")
