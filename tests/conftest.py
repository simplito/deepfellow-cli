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
def isolate_cli_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Keep every test away from the developer's real ~/.deepfellow config and secrets."""
    monkeypatch.setenv("DF_CLI_CONFIG_PATH", str(tmp_path / "config"))
    monkeypatch.setenv("DF_CLI_SECRETS_PATH", str(tmp_path / "secrets"))
    state.cli_config_file = tmp_path / "config"
    state.cli_secrets_file = tmp_path / "secrets"
    yield
    state.reset()
