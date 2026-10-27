# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

from deepfellow.infra.utils.validation import check_infra_directory


@mock.patch("deepfellow.infra.utils.validation.check_service_directory")
def test_check_infra_directory_delegates_to_check_service_directory(
    mock_check_service_directory: mock.MagicMock,
) -> None:
    directory = Path("/some/infra/dir")

    check_infra_directory(directory)

    assert mock_check_service_directory.call_count == 1
    assert mock_check_service_directory.call_args == mock.call(directory, "Infra", None)


@mock.patch("deepfellow.infra.utils.validation.check_service_directory")
def test_check_infra_directory_forwards_custom_missing_message(
    mock_check_service_directory: mock.MagicMock,
) -> None:
    directory = Path("/some/infra/dir")

    check_infra_directory(directory, missing_message="custom message")

    assert mock_check_service_directory.call_count == 1
    assert mock_check_service_directory.call_args == mock.call(directory, "Infra", "custom message")
