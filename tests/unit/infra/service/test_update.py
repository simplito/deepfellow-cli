# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from unittest import mock
from unittest.mock import Mock

import pytest
import typer
from typer.testing import CliRunner

from deepfellow.infra.service import app
from deepfellow.infra.utils.service_update import update
from deepfellow.infra.utils.update_spec import DockerTags

DOCKER_TAGS_FIELD = {"name": "image_version", "type": "docker-tags"}
OLLAMA = {
    "id": "ollama",
    "installed": {"hardware": "GPU", "image_version": "0.11.0"},
    "spec": {"fields": [DOCKER_TAGS_FIELD]},
}


@pytest.fixture(autouse=True)
def assume_yes() -> Iterator[None]:
    with mock.patch("deepfellow.infra.utils.update_spec.state", yes=True):
        yield


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress", return_value={"status": "OK"})
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_puts_merged_spec(mock_resolve: Mock, mock_get: Mock, mock_request: Mock, mock_echo: Mock) -> None:
    update(name="ollama", set_args=["hardware=CPU"], image_version="0.12.0")

    assert mock_request.call_count == 1
    assert mock_request.call_args.args[0] == "http://infra:8086/admin/services/ollama"
    assert mock_request.call_args.kwargs["method"] == "PUT"
    assert mock_request.call_args.kwargs["data"] == {"spec": {"hardware": "CPU", "image_version": "0.12.0"}}
    assert mock_echo.success.call_args == mock.call("Service ollama updated.")


@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_keeps_instance_separator_in_url(mock_resolve: Mock, mock_get: Mock, mock_request: Mock) -> None:
    mock_request.return_value = {"status": "OK"}

    update(name="ollama|cpu", image_version="0.12.0")

    assert mock_request.call_args.args[0] == "http://infra:8086/admin/services/ollama|cpu"


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_update.get", return_value={"id": "ollama", "installed": False})
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_when_service_not_installed(
    mock_resolve: Mock, mock_get: Mock, mock_request: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(name="ollama", image_version="0.12.0")

    assert mock_request.call_count == 0
    assert mock_echo.error.call_args == mock.call("'ollama' is not installed. Install it first.")


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress", return_value={"status": "OK"})
@mock.patch(
    "deepfellow.infra.utils.update_spec.fetch_docker_tags",
    return_value=DockerTags(image="ollama/ollama", tags=["0.12.0", "0.11.0"]),
)
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_without_version_picks_newest_release(
    mock_resolve: Mock, mock_get: Mock, mock_tags: Mock, mock_request: Mock, mock_echo: Mock
) -> None:
    update(name="ollama")

    assert mock_request.call_args.kwargs["data"] == {"spec": {"hardware": "GPU", "image_version": "0.12.0"}}


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.update_spec.fetch_docker_tags", return_value=DockerTags(image="x", tags=["dev"]))
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_when_no_release_version_listed(
    mock_resolve: Mock, mock_get: Mock, mock_tags: Mock, mock_request: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(name="ollama")

    assert mock_request.call_count == 0
    assert mock_echo.error.call_args == mock.call(
        "Infra lists no release version matching the installed one of 'ollama'. "
        "Choose one with --image-version; `versions` lists the tags."
    )


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_rejects_spec_with_set(mock_resolve: Mock, mock_get: Mock, mock_request: Mock, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        update(name="ollama", spec="{}", set_args=["hardware=CPU"])

    assert mock_request.call_count == 0
    assert mock_echo.error.call_args == mock.call("--spec and --set cannot be used together. Use one or the other.")


@mock.patch("deepfellow.infra.service.update.update_util")
def test_update_command_passes_options(mock_update: Mock) -> None:
    result = CliRunner().invoke(app, ["update", "ollama", "--image-version", "0.12.0"])

    assert result.exit_code == 0
    assert mock_update.call_args == mock.call(
        name="ollama", server=None, spec=None, set_args=None, image_version="0.12.0"
    )


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_skips_call_when_settings_unchanged(
    mock_resolve: Mock, mock_get: Mock, mock_request: Mock, mock_echo: Mock
) -> None:
    update(name="ollama", image_version="0.11.0")

    assert mock_request.call_count == 0
    assert mock_echo.info.call_args == mock.call("Service 'ollama' already has these settings; nothing to update.")


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch("deepfellow.infra.utils.service_update.confirm_version_change", return_value=False)
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_stops_when_user_declines(
    mock_resolve: Mock, mock_get: Mock, mock_confirm: Mock, mock_request: Mock, mock_echo: Mock
) -> None:
    update(name="ollama", image_version="0.12.0")

    assert mock_request.call_count == 0
    assert mock_echo.info.call_args == mock.call("Update cancelled.")


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch(
    "deepfellow.infra.utils.service_update.install_with_progress", return_value={"status": "error", "details": "boom"}
)
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_on_error_status(mock_resolve: Mock, mock_get: Mock, mock_request: Mock, mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        update(name="ollama", image_version="0.12.0")

    assert mock_echo.error.call_args == mock.call("Unable to update service. boom")


@mock.patch("deepfellow.infra.utils.service_update.echo")
@mock.patch("deepfellow.infra.utils.service_update.cancel_service_install")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress", side_effect=KeyboardInterrupt)
@mock.patch("deepfellow.infra.utils.service_update.get", return_value=OLLAMA)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_cancels_on_infra_when_interrupted(
    mock_resolve: Mock, mock_get: Mock, mock_install: Mock, mock_cancel: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(KeyboardInterrupt):
        update(name="ollama", image_version="0.12.0")

    assert mock_cancel.call_args == mock.call("http://infra:8086", "key", "ollama")


@mock.patch("deepfellow.infra.utils.update_spec.echo")
@mock.patch("deepfellow.infra.utils.service_update.install_with_progress")
@mock.patch(
    "deepfellow.infra.utils.service_update.get",
    return_value={"id": "x", "installed": {"image_version": "1.0.0"}, "spec": {"fields": []}},
)
@mock.patch("deepfellow.infra.utils.service_update.resolve_infra_connection", return_value=("http://infra:8086", "key"))
def test_update_fails_for_service_without_docker_tags_field(
    mock_resolve: Mock, mock_get: Mock, mock_install: Mock, mock_echo: Mock
) -> None:
    with pytest.raises(typer.Exit):
        update(name="x")

    assert mock_install.call_count == 0
