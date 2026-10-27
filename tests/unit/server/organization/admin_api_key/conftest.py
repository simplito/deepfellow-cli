# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import pytest

from deepfellow.server.organization.admin_api_key.utils import ApiKey, Owner


@pytest.fixture
def api_key() -> ApiKey:
    return ApiKey(
        id="key-id",
        object="organization.admin_api_key",
        name="my-key",
        redacted_value="sk-***",
        owner=Owner(
            created_at=0.0,
            id="owner-id",
            name="owner",
            object="organization.user",
            role="admin",
            type="user",
        ),
        created_at=0.0,
        last_used_at=0.0,
        value=None,
    )
