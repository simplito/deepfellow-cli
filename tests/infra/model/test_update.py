# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.infra.model import app
from deepfellow.infra.utils.model_update import update
from deepfellow.infra.utils.update_spec import DockerTags

DOCKER_TAGS_FIELD = {"name": "image_version", "type": "docker-tags"}
INSTALLED_CHUNKER = {
    "id": "doc_chunker",
    "type": "custom",
    "installed": {"registration_id": "abc", "spec": {"prefix": "doc_chunker", "image_version": "v2.2.0"}},
    "spec": {"fields": [DOCKER_TAGS_FIELD]},
}


@pytest.fixture(autouse=True)
def assume_yes() -> Iterator[None]:
    with mock.patch("deepfellow.infra.utils.update_spec.state", yes=True):
        yield


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_sends_merged_spec_to_edit_endpoint(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    update(service_name="custom", model_name="doc_chunker", image_version="v2.4.0")

    assert mock_install.call_count == 1
    assert (
        mock_install.call_args.args[0] == "http://infra:8086/admin/services/custom/models/_/edit?model_id=doc_chunker"
    )
    assert mock_install.call_args.kwargs["data"] == {"spec": {"prefix": "doc_chunker", "image_version": "v2.4.0"}}
    assert mock_echo.success.call_args == mock.call("Model doc_chunker updated.")


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_skips_call_when_settings_unchanged(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    update(service_name="custom", model_name="doc_chunker", image_version="v2.2.0")

    assert mock_install.call_count == 0
    assert mock_echo.info.call_count == 1


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_for_unknown_model(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(service_name="custom", model_name="nope", image_version="v2.4.0")

    assert mock_install.call_count == 0
    assert mock_echo.error.call_args == mock.call("Model 'nope' not found in service 'custom'.")


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_update.get_service_models",
    return_value=[{"id": "doc_chunker", "type": "custom", "installed": False}],
)
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_when_model_not_installed(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(service_name="custom", model_name="doc_chunker", image_version="v2.4.0")

    assert mock_install.call_count == 0
    assert mock_echo.error.call_args == mock.call("'doc_chunker' is not installed. Install it first.")


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch(
    "deepfellow.infra.utils.model_update.install_with_progress", return_value={"status": "error", "details": "boom"}
)
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_on_error_status(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(service_name="custom", model_name="doc_chunker", image_version="v2.4.0")

    assert mock_echo.error.call_args == mock.call("Unable to update model. boom")


@mock.patch("deepfellow.infra.model.update.update_util")
def test_update_command_passes_options(mock_update: Mock) -> None:
    result = CliRunner().invoke(
        app, ["update", "custom", "doc_chunker", "--image-version", "v2.4.0", "--set", "max_concurrent=4"]
    )

    assert result.exit_code == 0
    assert mock_update.call_args == mock.call(
        service_name="custom",
        model_name="doc_chunker",
        server=None,
        spec=None,
        set_args=["max_concurrent=4"],
        image_version="v2.4.0",
    )


TAGS = DockerTags(image="hub/doc-chunker-gpu", tags=["v2.4.0", "v2.3.0-volta", "v2.3.0", "v2.2.0"], default="v2.4.0")


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags", return_value=TAGS)
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_without_version_picks_newest_release(
    mock_resolve: Mock, mock_models: Mock, mock_tags: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    update(service_name="custom", model_name="doc_chunker")

    assert mock_tags.call_args == mock.call(
        "http://infra:8086", "key", "custom", {"prefix": "doc_chunker", "image_version": "v2.2.0"}, "doc_chunker"
    )
    assert mock_install.call_args.kwargs["data"] == {"spec": {"prefix": "doc_chunker", "image_version": "v2.4.0"}}


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags")
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_with_other_changes_keeps_image(
    mock_resolve: Mock, mock_models: Mock, mock_tags: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    update(service_name="custom", model_name="doc_chunker", set_args=["max_concurrent=4"])

    assert mock_tags.call_count == 0
    assert mock_install.call_args.kwargs["data"] == {
        "spec": {"prefix": "doc_chunker", "image_version": "v2.2.0", "max_concurrent": "4"}
    }


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.update_spec.state", yes=False)
@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags", return_value=TAGS)
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_stops_when_user_declines(
    mock_resolve: Mock,
    mock_models: Mock,
    mock_tags: Mock,
    mock_state: Mock,
    mock_spec_echo: Mock,
    mock_install: Mock,
    mock_echo: Mock,
) -> None:
    mock_spec_echo.confirm.return_value = False

    update(service_name="custom", model_name="doc_chunker")

    assert mock_spec_echo.confirm.call_args == mock.call("Update 'doc_chunker' from v2.2.0 to v2.4.0?", default=True)
    assert mock_install.call_count == 0
    assert mock_echo.info.call_args == mock.call("Update cancelled.")


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.model_update.get_service_models",
    return_value=[{**INSTALLED_CHUNKER, "id": "llama3.1:8b", "spec": {"fields": []}}],
)
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_for_model_without_docker_tags_field(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(service_name="ollama", model_name="llama3.1:8b")

    assert mock_install.call_count == 0
    assert mock_echo.error.call_args == mock.call(
        "'llama3.1:8b' has no Docker image version setting. Change its settings with --set or --spec."
    )


@mock.patch("deepfellow.infra.utils.model_update.echo")
@mock.patch("deepfellow.infra.utils.model_update.cancel_model_install")
@mock.patch("deepfellow.infra.utils.model_update.install_with_progress", side_effect=KeyboardInterrupt)
@mock.patch("deepfellow.infra.utils.model_update.get_service_models", return_value=[INSTALLED_CHUNKER])
@mock.patch("deepfellow.infra.utils.model_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_cancels_on_infra_when_interrupted(
    mock_resolve: Mock, mock_models: Mock, mock_install: Mock, mock_cancel: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(KeyboardInterrupt):
        update(service_name="custom", model_name="doc_chunker", image_version="v2.4.0")

    assert mock_cancel.call_args == mock.call("http://infra:8086", "key", "custom", "doc_chunker")
