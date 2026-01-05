# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Time related utils."""

from datetime import datetime

from tzlocal.unix import get_localzone


def datetime_to_str(value: float) -> str:
    """Convert float representing datetime to a localized date string."""
    return str(datetime.fromtimestamp(value, tz=get_localzone()))
