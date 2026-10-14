# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from typer.testing import CliRunner

from deepfellow.infra.model import app

CONNECTION = ("http://infra:8086", "key")


@mock.patch("deepfellow.infra.model.versions.show_versions")
@mock.patch(
    "deepfellow.infra.model.versions.get_service_models",
    return_value=[{"id": "doc_chunker", "installed": {"registration_id": "a", "spec": {"hardware": "GPU"}}}],
)
@mock.patch("deepfellow.infra.model.versions.resolve_infra_connection", return_value=CONNECTION)
def test_model_versions_shows_versions_for_installed_model(
    mock_resolve: Mock, mock_models: Mock, mock_show: Mock
) -> None:
    result = CliRunner().invoke(app, ["versions", "custom", "doc_chunker"])

    assert result.exit_code == 0
    assert mock_show.call_args == mock.call(*CONNECTION, "custom", {"hardware": "GPU"}, model_id="doc_chunker")


@mock.patch("deepfellow.infra.model.versions.show_versions")
@mock.patch(
    "deepfellow.infra.model.versions.get_service_models", return_value=[{"id": "doc_chunker", "installed": False}]
)
@mock.patch("deepfellow.infra.model.versions.resolve_infra_connection", return_value=CONNECTION)
def test_model_versions_works_for_model_that_is_not_installed(
    mock_resolve: Mock, mock_models: Mock, mock_show: Mock
) -> None:
    result = CliRunner().invoke(app, ["versions", "custom", "doc_chunker"])

    assert result.exit_code == 0
    assert mock_show.call_args == mock.call(*CONNECTION, "custom", None, model_id="doc_chunker")


@mock.patch("deepfellow.infra.model.versions.show_versions")
@mock.patch("deepfellow.infra.model.versions.echo")
@mock.patch("deepfellow.infra.model.versions.get_service_models", return_value=[])
@mock.patch("deepfellow.infra.model.versions.resolve_infra_connection", return_value=CONNECTION)
def test_model_versions_fails_for_unknown_model(
    mock_resolve: Mock, mock_models: Mock, mock_echo: Mock, mock_show: Mock
) -> None:
    result = CliRunner().invoke(app, ["versions", "custom", "nope"])

    assert result.exit_code == 1
    assert mock_show.call_count == 0
    assert mock_echo.error.call_args == mock.call("Model 'nope' not found in service 'custom'.")
