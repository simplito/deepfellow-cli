# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from unittest import mock
from unittest.mock import Mock

import pytest

from deepfellow.common.colors import COLORTERM, get_color_support


@mock.patch("deepfellow.common.colors.sys.stdout.isatty")
def test_get_color_support_returns_limited_when_not_a_tty(mock_isatty: Mock) -> None:
    mock_isatty.return_value = False

    result = get_color_support()

    assert result == COLORTERM.limited


@pytest.mark.parametrize(
    ("colorterm", "term", "expected"),
    [
        ("truecolor", "", COLORTERM.truecolor),
        ("24bit", "", COLORTERM.truecolor),
        ("", "xterm-truecolor", COLORTERM.truecolor),
        ("", "xterm-24bit", COLORTERM.truecolor),
        ("", "xterm-256color", COLORTERM.limited),
        ("unsupported", "xterm-256color", COLORTERM.limited),
    ],
)
@mock.patch("deepfellow.common.colors.sys.stdout.isatty")
def test_get_color_support_detects_support_from_environment(
    mock_isatty: Mock,
    colorterm: str,
    term: str,
    expected: COLORTERM,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_isatty.return_value = True
    monkeypatch.setenv("COLORTERM", colorterm)
    monkeypatch.setenv("TERM", term)

    result = get_color_support()

    assert result == expected
