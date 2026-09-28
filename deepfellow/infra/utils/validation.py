# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Validate infra data."""

from pathlib import Path

from deepfellow.common.system import check_service_directory


def check_infra_directory(directory: Path, missing_message: str | None = None) -> None:
    """Check if directory exist."""
    check_service_directory(directory, "Infra", missing_message)
