# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
import typer

from deepfellow.common.validation import validate_password


def test_validate_password_none_returns_none():
    assert validate_password(None) is None


@pytest.mark.parametrize(
    "password",
    [
        "abcdefgh",  # minimal valid length
        "Abc123456",  # alphanumeric
        "a1!@#$%^&*()-_=+",  # all allowed special chars
        "Password123_+=",
    ],
)
def test_validate_password_valid(password):
    assert validate_password(password) == password


@pytest.mark.parametrize(
    "password",
    [
        "",  # empty
        "short",  # too short
        "no$pecials?",  # contains '?'
        "toolongpassword123456789",  # too long (20+)
    ],
)
def test_validate_password_invalid(password):
    with pytest.raises(typer.BadParameter):
        validate_password(password)
