# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def no_real_config_json():
    """Isolate tests from whatever config.json happens to exist on the machine running them.

    DF_INFRA_STORAGE_DIR (the fallback when a test's .env doesn't set DF_INFRA_STORAGE_DIR) is a
    fixed absolute path, not scoped to a test's tmp_path, so an unmocked inspect() would read this
    machine's real ~/.deepfellow/infra/storage/config.json (if installed) instead of an
    empty/synthetic one. Tests exercising the config.json-aware merge override this with their own
    mock.patch on the same target.
    """
    with mock.patch("deepfellow.infra.utils.install.read_config_json_settings", return_value={}):
        yield


@pytest.fixture(autouse=True)
def mock_write_ca_trust_bundle() -> Iterator[mock.MagicMock]:
    """Isolate install tests from the machine's real CA (`~/.deepfellow/ca`) and from writing a trust bundle.

    Tests that check the bundle is written request this fixture by name and assert on the mock.
    """
    with mock.patch("deepfellow.infra.utils.install.write_ca_trust_bundle") as mock_write:
        yield mock_write
