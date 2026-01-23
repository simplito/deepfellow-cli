# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Validate infra data."""

from pathlib import Path

from deepfellow.common.system import check_service_directory


def check_server_directory(directory: Path) -> None:
    """Check if directory exist."""
    check_service_directory(directory, "Server")
