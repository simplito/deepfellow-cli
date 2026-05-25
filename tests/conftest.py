# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest.mock import Mock

import pytest
from typer import Context


@pytest.fixture
def context() -> Context:
    ctx = Mock(spec=Context)
    ctx.obj = {}
    return ctx


@pytest.fixture
def directory() -> Path:
    return Path("/fake/dir")
