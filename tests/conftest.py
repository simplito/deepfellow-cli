# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path

import pytest

from deepfellow.common.state import state


@pytest.fixture
def directory() -> Path:
    return Path("/fake/dir")


@pytest.fixture(autouse=True)
def reset_app_state():
    yield
    state.reset()
