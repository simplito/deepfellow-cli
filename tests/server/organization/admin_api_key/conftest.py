# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

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
