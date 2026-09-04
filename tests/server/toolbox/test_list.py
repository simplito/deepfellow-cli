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

from deepfellow.server.toolbox.list import list
from deepfellow.server.toolbox.utils import Toolbox


@mock.patch("deepfellow.server.toolbox.list.echo.info")
@mock.patch("deepfellow.server.toolbox.list.list_toolboxes")
@mock.patch("deepfellow.server.toolbox.list.get_token")
@mock.patch("deepfellow.server.toolbox.list.get_server_url")
@mock.patch("deepfellow.server.toolbox.list.state")
def test_list_prints_toolboxes_joined_by_double_newline(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_toolboxes: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    toolboxes = [
        Toolbox(id="toolbox-1", name="First", project_id="project-id", created_at=0),
        Toolbox(id="toolbox-2", name="Second", project_id="project-id", created_at=0),
    ]
    mock_list_toolboxes.return_value = toolboxes

    list(project_id="project-id", server=None, organization_id="org-id", limit=100, after=None, before=None)

    assert mock_list_toolboxes.call_count == 1
    assert mock_list_toolboxes.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", limit=100, after=None, before=None
    )
    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(f"{toolboxes[0]}\n\n{toolboxes[1]}")


@mock.patch("deepfellow.server.toolbox.list.echo.info")
@mock.patch("deepfellow.server.toolbox.list.list_toolboxes")
@mock.patch("deepfellow.server.toolbox.list.get_token")
@mock.patch("deepfellow.server.toolbox.list.get_server_url")
@mock.patch("deepfellow.server.toolbox.list.state")
def test_list_passes_after_and_before_to_list_toolboxes(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_toolboxes: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_toolboxes.return_value = []

    list(
        project_id="project-id", server=None, organization_id="org-id", limit=100, after="after-id", before="before-id"
    )

    assert mock_list_toolboxes.call_args == mock.call(
        "https://server", "token", "project-id", "org-id", limit=100, after="after-id", before="before-id"
    )


@mock.patch("deepfellow.server.toolbox.list.echo.info")
@mock.patch("deepfellow.server.toolbox.list.list_toolboxes")
@mock.patch("deepfellow.server.toolbox.list.get_token")
@mock.patch("deepfellow.server.toolbox.list.get_server_url")
@mock.patch("deepfellow.server.toolbox.list.state")
def test_list_prints_message_when_no_toolboxes(
    mock_state: Mock,
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_list_toolboxes: Mock,
    mock_info: Mock,
) -> None:
    mock_state.cli_secrets_file = "secrets-file"
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_list_toolboxes.return_value = []

    list(project_id="project-id", server=None, organization_id="org-id", limit=100)

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call("No toolboxes found.")
