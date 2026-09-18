# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.server.project.update import update
from deepfellow.server.project.utils import Project


def _project(**overrides: Any) -> Project:
    defaults: dict[str, Any] = {
        "name": "Acme",
        "id": "proj-id",
        "status": "active",
        "models": "all",
        "custom_endpoints": [],
        "mcp_prefixes": [],
        "created_at": 0.0,
    }
    defaults.update(overrides)
    return Project(**defaults)


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_calls_update_project_with_name_only(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name="Renamed",
        models=None,
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"name": "Renamed"}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_adds_model_to_existing_models(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(models=["gpt-4"])
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=["gpt-3.5"],
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 1
    assert mock_get_project.call_args == mock.call("https://server", "token", "org-id", "project-id")
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"models": ["gpt-4", "gpt-3.5"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_dedups_model_already_present(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(models=["gpt-4", "gpt-3.5"])
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=["gpt-3.5", "claude"],
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"models": ["gpt-4", "gpt-3.5", "claude"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_replaces_models_when_overwrite_flag_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=["gpt-4"],
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=True,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"models": ["gpt-4"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_treats_all_as_all_models_keyword_without_fetching_current(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=["all"],
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"models": "all"}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_all_mixed_with_specific_models(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=["all", "gpt-4"],
            custom_endpoints=None,
            mcp_prefixes=None,
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_adding_to_all_sentinel_models(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(models="all")

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=["gpt-4"],
            custom_endpoints=None,
            mcp_prefixes=None,
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_adds_custom_endpoint_to_existing_custom_endpoints(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(custom_endpoints=["ep-a"])
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=["ep-b"],
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"custom_endpoints": ["ep-a", "ep-b"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_replaces_custom_endpoints_when_overwrite_flag_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=["ep-c"],
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=True,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"custom_endpoints": ["ep-c"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_adding_to_all_sentinel_custom_endpoints(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(custom_endpoints="all")

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=None,
            custom_endpoints=["ep-a"],
            mcp_prefixes=None,
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_treats_all_as_all_custom_endpoints_keyword_without_fetching_current(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=["all"],
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"custom_endpoints": "all"}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_all_mixed_with_specific_custom_endpoints(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=None,
            custom_endpoints=["all", "ep-a"],
            mcp_prefixes=None,
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_adds_mcp_prefix_to_existing_mcp_prefixes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(mcp_prefixes=["ocr-websearch"])
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=None,
        mcp_prefixes=["brave-search"],
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"mcp_prefixes": ["ocr-websearch", "brave-search"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_replaces_mcp_prefixes_when_overwrite_flag_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=None,
        mcp_prefixes=["brave-search"],
        webhook_url=None,
        webhook_secret=None,
        overwrite=True,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"mcp_prefixes": ["brave-search"]}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_treats_all_as_all_mcp_prefixes_keyword_without_fetching_current(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=None,
        mcp_prefixes=["all"],
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server", "token", "org-id", "project-id", {"mcp_prefixes": "all"}
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_all_mixed_with_specific_mcp_prefixes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=None,
            custom_endpoints=None,
            mcp_prefixes=["all", "brave-search"],
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_adding_to_all_sentinel_mcp_prefixes(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(mcp_prefixes="all")

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=None,
            custom_endpoints=None,
            mcp_prefixes=["brave-search"],
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_fetches_current_project_once_for_multiple_list_fields(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_get_project.return_value = _project(
        models=["gpt-4"], custom_endpoints=["ep-a"], mcp_prefixes=["ocr-websearch"]
    )
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name="Renamed",
        models=["gpt-3.5"],
        custom_endpoints=["ep-b"],
        mcp_prefixes=["brave-search"],
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_get_project.call_count == 1
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server",
        "token",
        "org-id",
        "project-id",
        {
            "name": "Renamed",
            "models": ["gpt-4", "gpt-3.5"],
            "custom_endpoints": ["ep-a", "ep-b"],
            "mcp_prefixes": ["ocr-websearch", "brave-search"],
        },
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_includes_webhook_url_and_secret_when_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    mock_update_project.return_value = _project()

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name=None,
        models=None,
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url="https://example.com/hook",
        webhook_secret="s3cr3t",
        overwrite=False,
    )

    assert mock_get_project.call_count == 0
    assert mock_update_project.call_count == 1
    assert mock_update_project.call_args == mock.call(
        "https://server",
        "token",
        "org-id",
        "project-id",
        {"webhook_url": "https://example.com/hook", "webhook_secret": "s3cr3t"},
    )


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_raises_bad_parameter_when_no_fields_given(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"

    with pytest.raises(typer.BadParameter):
        update(
            server=None,
            organization_id="org-id",
            project_id="project-id",
            name=None,
            models=None,
            custom_endpoints=None,
            mcp_prefixes=None,
            webhook_url=None,
            webhook_secret=None,
            overwrite=False,
        )

    assert mock_update_project.call_count == 0


@mock.patch("deepfellow.server.project.update.echo.info")
@mock.patch("deepfellow.server.project.update.update_project")
@mock.patch("deepfellow.server.project.update.get_project")
@mock.patch("deepfellow.server.project.update.get_token")
@mock.patch("deepfellow.server.project.update.get_server_url")
def test_update_echoes_updated_project(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_get_project: Mock,
    mock_update_project: Mock,
    mock_info: Mock,
) -> None:
    mock_get_server_url.return_value = "https://server"
    mock_get_token.return_value = "token"
    project = _project()
    mock_update_project.return_value = project

    update(
        server=None,
        organization_id="org-id",
        project_id="project-id",
        name="Renamed",
        models=None,
        custom_endpoints=None,
        mcp_prefixes=None,
        webhook_url=None,
        webhook_secret=None,
        overwrite=False,
    )

    assert mock_info.call_count == 1
    assert mock_info.call_args == mock.call(str(project))
