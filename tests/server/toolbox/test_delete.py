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

from deepfellow.server.toolbox.delete import delete
from deepfellow.server.toolbox.utils import Toolbox


@pytest.fixture
def toolbox() -> Toolbox:
    return Toolbox(id="toolbox-id", name="Toolbox Name", project_id="project-id", created_at=0)


@mock.patch("deepfellow.server.toolbox.delete.state")
@mock.patch("deepfellow.server.toolbox.delete.echo.debug")
@mock.patch("deepfellow.server.toolbox.delete.echo.success")
@mock.patch("deepfellow.server.toolbox.delete.echo.confirm")
@mock.patch("deepfellow.server.toolbox.delete.delete_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_token")
@mock.patch("deepfellow.server.toolbox.delete.get_server_url")
def test_delete_calls_delete_toolbox_when_confirmed(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_toolbox: Mock,
    mock_delete_toolbox: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    toolbox: Toolbox,
) -> None:
    mock_state.yes = False
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_toolbox.return_value = toolbox
    mock_confirm.return_value = True

    delete(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id")

    assert mock_delete_toolbox.call_count == 1
    assert mock_delete_toolbox.call_args == mock.call("https://server", "token", "project-id", "org-id", "toolbox-id")
    assert mock_success.call_args == mock.call(f"Toolbox '{toolbox.name}' deleted.")


@mock.patch("deepfellow.server.toolbox.delete.state")
@mock.patch("deepfellow.server.toolbox.delete.echo.debug")
@mock.patch("deepfellow.server.toolbox.delete.echo.success")
@mock.patch("deepfellow.server.toolbox.delete.echo.confirm")
@mock.patch("deepfellow.server.toolbox.delete.delete_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_token")
@mock.patch("deepfellow.server.toolbox.delete.get_server_url")
def test_delete_raises_exit_when_declined(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_toolbox: Mock,
    mock_delete_toolbox: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    toolbox: Toolbox,
) -> None:
    mock_state.yes = False
    mock_get_toolbox.return_value = toolbox
    mock_confirm.return_value = False

    with pytest.raises(typer.Exit) as exc_info:
        delete(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id")

    assert exc_info.value.exit_code == 1
    assert mock_delete_toolbox.call_count == 0


@mock.patch("deepfellow.server.toolbox.delete.state")
@mock.patch("deepfellow.server.toolbox.delete.echo.debug")
@mock.patch("deepfellow.server.toolbox.delete.echo.success")
@mock.patch("deepfellow.server.toolbox.delete.echo.confirm")
@mock.patch("deepfellow.server.toolbox.delete.delete_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_toolbox")
@mock.patch("deepfellow.server.toolbox.delete.get_token")
@mock.patch("deepfellow.server.toolbox.delete.get_server_url")
def test_delete_skips_confirm_prompt_when_yes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_toolbox: Mock,
    mock_delete_toolbox: Mock,
    mock_confirm: Mock,
    mock_success: Mock,
    mock_debug: Mock,
    mock_state: Mock,
    toolbox: Toolbox,
) -> None:
    mock_state.yes = True
    mock_get_toolbox.return_value = toolbox

    delete(project_id="project-id", toolbox_id="toolbox-id", server=None, organization_id="org-id")

    assert mock_confirm.call_count == 0
    assert mock_delete_toolbox.call_count == 1
    assert mock_debug.call_count == 1
    assert mock_debug.call_args == mock.call("Automatically confirming the delete.")
