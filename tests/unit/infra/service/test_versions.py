# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from typer.testing import CliRunner

from deepfellow.infra.service import app

CONNECTION = ("http://infra:8086", "key")


@mock.patch("deepfellow.infra.service.versions.show_versions")
@mock.patch("deepfellow.infra.service.versions.call_infra", return_value={"installed": {"hardware": "CPU"}})
@mock.patch("deepfellow.infra.service.versions.resolve_infra_connection", return_value=CONNECTION)
def test_service_versions_shows_versions_for_installed_service(
    mock_resolve: Mock, mock_call: Mock, mock_show: Mock
) -> None:
    result = CliRunner().invoke(app, ["versions", "ollama"])

    assert result.exit_code == 0
    assert mock_show.call_args == mock.call(*CONNECTION, "ollama", {"hardware": "CPU"})


@mock.patch("deepfellow.infra.service.versions.show_versions")
@mock.patch("deepfellow.infra.service.versions.call_infra", return_value={"installed": False})
@mock.patch("deepfellow.infra.service.versions.resolve_infra_connection", return_value=CONNECTION)
def test_service_versions_works_for_service_that_is_not_installed(
    mock_resolve: Mock, mock_call: Mock, mock_show: Mock
) -> None:
    result = CliRunner().invoke(app, ["versions", "ollama"])

    assert result.exit_code == 0
    assert mock_show.call_args == mock.call(*CONNECTION, "ollama", None)
