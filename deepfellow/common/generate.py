# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generators."""

import secrets
import string


def generate_password(length: int = 16) -> str:
    """Generate password."""
    # Define the characters to choose from
    alphabet = string.ascii_letters + string.digits

    # Generate a random password using secrets
    password = "".join(secrets.choice(alphabet) for i in range(length))
    return password  # noqa: RET504
