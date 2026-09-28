# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Validate infra data."""

from pathlib import Path

from deepfellow.common.system import check_service_directory


def check_server_directory(directory: Path) -> None:
    """Check if directory exist."""
    check_service_directory(directory, "Server")
