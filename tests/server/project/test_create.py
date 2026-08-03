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

from deepfellow.server.project.create import Status, create
from deepfellow.server.project.utils import Project


def _project() -> Project:
    return Project(
        name="Acme",
        id="proj-id",
        status="active",
        models="all",
        custom_endpoints=[],
        mcp_prefixes=[],
        created_at=0.0,
    )


@mock.patch("deepfellow.server.project.create.echo.info")
@mock.patch("deepfellow.server.project.create.create_project")
@mock.patch("deepfellow.server.project.create.get_token")
@mock.patch("deepfellow.server.project.create.get_server_url")
def test_create_calls_create_project_with_all_models_when_no_models_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_create_project.return_value = _project()

    create(
        server=None,
        organization_id="org-id",
        name="Acme",
        status=Status.active,
        models=None,
        custom_endpoints=[],
    )

    assert mock_create_project.call_count == 1
    assert mock_create_project.call_args == mock.call(
        "https://server",
        "token",
        "org-id",
        {
            "name": "Acme",
            "status": Status.active,
            "models": "all",
            "custom_endpoints": [],
        },
    )


@mock.patch("deepfellow.server.project.create.echo.info")
@mock.patch("deepfellow.server.project.create.create_project")
@mock.patch("deepfellow.server.project.create.get_token")
@mock.patch("deepfellow.server.project.create.get_server_url")
def test_create_calls_create_project_with_specific_models(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_create_project.return_value = _project()

    create(
        server=None,
        organization_id="org-id",
        name="Acme",
        status=Status.active,
        models=["gpt-4", "gpt-3.5"],
        custom_endpoints=[],
    )

    assert mock_create_project.call_count == 1
    assert mock_create_project.call_args == mock.call(
        "https://server",
        "token",
        "org-id",
        {
            "name": "Acme",
            "status": Status.active,
            "models": ["gpt-4", "gpt-3.5"],
            "custom_endpoints": [],
        },
    )


@mock.patch("deepfellow.server.project.create.echo.info")
@mock.patch("deepfellow.server.project.create.create_project")
@mock.patch("deepfellow.server.project.create.get_token")
@mock.patch("deepfellow.server.project.create.get_server_url")
def test_create_treats_all_as_all_models_keyword(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_create_project.return_value = _project()

    create(
        server=None,
        organization_id="org-id",
        name="Acme",
        status=Status.active,
        models=["all"],
        custom_endpoints=[],
    )

    assert mock_create_project.call_count == 1
    assert mock_create_project.call_args == mock.call(
        "https://server",
        "token",
        "org-id",
        {
            "name": "Acme",
            "status": Status.active,
            "models": "all",
            "custom_endpoints": [],
        },
    )


@mock.patch("deepfellow.server.project.create.echo.info")
@mock.patch("deepfellow.server.project.create.create_project")
@mock.patch("deepfellow.server.project.create.get_token")
@mock.patch("deepfellow.server.project.create.get_server_url")
def test_create_raises_bad_parameter_when_all_mixed_with_specific_models(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"

    with pytest.raises(typer.BadParameter):
        create(
            server=None,
            organization_id="org-id",
            name="Acme",
            status=Status.active,
            models=["all", "gpt-4"],
            custom_endpoints=[],
        )

    assert mock_create_project.call_count == 0


@mock.patch("deepfellow.server.project.create.echo.info")
@mock.patch("deepfellow.server.project.create.create_project")
@mock.patch("deepfellow.server.project.create.get_token")
@mock.patch("deepfellow.server.project.create.get_server_url")
def test_create_echoes_created_project(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_create_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    project = _project()
    mock_create_project.return_value = project

    create(
        server=None,
        organization_id="org-id",
        name="Acme",
        status=Status.active,
        models=None,
        custom_endpoints=[],
    )

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(project))
