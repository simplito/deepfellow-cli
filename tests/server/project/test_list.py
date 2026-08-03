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

from deepfellow.server.project.list import list
from deepfellow.server.project.utils import Project


@mock.patch("deepfellow.server.project.list.echo.info")
@mock.patch("deepfellow.server.project.list.list_projects")
@mock.patch("deepfellow.server.project.list.get_token")
@mock.patch("deepfellow.server.project.list.get_server_url")
@mock.patch("deepfellow.server.project.list.state")
def test_list_prints_projects_joined_by_double_newline(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_projects: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    projects = [
        Project(
            name="Acme",
            id="proj-1",
            status="active",
            models=["gpt-4"],
            custom_endpoints=[],
            mcp_prefixes=[],
            created_at=0.0,
        ),
        Project(
            name="Globex",
            id="proj-2",
            status="archived",
            models=["gpt-4"],
            custom_endpoints=[],
            mcp_prefixes=[],
            created_at=0.0,
        ),
    ]
    mock_list_projects.return_value = projects

    list(server=None, organization_id="org-1")

    assert mock_get_token.call_count == 1
    assert mock_get_token.call_args == mock.call("secrets-file", "https://server")
    assert mock_list_projects.call_count == 1
    assert mock_list_projects.call_args == mock.call("https://server", "token", "org-1")
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(f"{projects[0]}\n\n{projects[1]}")


@mock.patch("deepfellow.server.project.list.echo.info")
@mock.patch("deepfellow.server.project.list.list_projects")
@mock.patch("deepfellow.server.project.list.get_token")
@mock.patch("deepfellow.server.project.list.get_server_url")
@mock.patch("deepfellow.server.project.list.state")
def test_list_prints_empty_string_when_no_projects(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_projects: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_projects.return_value = []

    list(server=None, organization_id="org-1")

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("")
