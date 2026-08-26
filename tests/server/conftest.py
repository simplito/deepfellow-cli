# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock

import pytest


@pytest.fixture(autouse=True)
def no_real_config_json():
    """Isolate tests from whatever config.json happens to exist on the machine running them.

    DF_SERVER_STORAGE_DIRECTORY is a fixed absolute path, not scoped to a test's tmp_path, so an
    unmocked inspect() would read this machine's real ~/.deepfellow/server/storage/config.json (if
    installed) instead of an empty/synthetic one - both for the values it merges and for the
    shared-storage warning's existence check. Tests exercising either override this with their own
    mock.patch on the same target.
    """
    with (
        mock.patch("deepfellow.server.utils.install.read_config_json_settings", return_value={}),
        mock.patch("deepfellow.server.utils.install.config_json_exists", return_value=False),
    ):
        yield
