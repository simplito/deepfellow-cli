# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from unittest import mock

import pytest


@pytest.fixture
def _unversioned_cli() -> Iterator[None]:
    """Pretend to be a dev build of the CLI, so image tags in tests aren't filtered by compatibility."""
    with mock.patch("deepfellow.common.version.cli_version", return_value="unknown"):
        yield
