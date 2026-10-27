# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path
from unittest import mock

from deepfellow.server.nightshift.status import status


@mock.patch("deepfellow.server.nightshift.status.print_nightshift_status")
@mock.patch("deepfellow.server.nightshift.status.assert_docker")
@mock.patch("deepfellow.server.nightshift.status.check_server_directory")
def test_status_delegates_to_shared_print_nightshift_status(
    mock_check_server_directory: mock.MagicMock,
    mock_assert_docker: mock.MagicMock,
    mock_print_nightshift_status: mock.MagicMock,
    directory: Path,
) -> None:
    """The actual mode/schedule/container-state rendering lives in print_nightshift_status() -
    shared with `server status`, which shows the same info alongside the server's own status -
    so the two commands never drift into two different renderings. See
    tests/unit/server/utils/test_docker.py for the rendering behavior itself."""
    status(directory=directory)

    assert mock_check_server_directory.call_args == mock.call(directory)
    assert mock_assert_docker.call_count == 1
    assert mock_print_nightshift_status.call_args == mock.call(directory)
