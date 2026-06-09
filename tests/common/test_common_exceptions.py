# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the exceptions module."""

from collections.abc import Callable

import pytest
import typer

from deepfellow.common.exceptions import reraise_if_debug
from deepfellow.common.state import state


def _call_reraise(exc_factory: Callable) -> None:
    try:
        exc_factory()
    except Exception as e:
        reraise_if_debug(e)


def _raise_value_error() -> None:
    raise ValueError("original")


def _raise_runtime_error() -> None:
    raise RuntimeError("boom")


def test_reraise_if_debug_reraises_original_exception_when_debug_true():
    state.debug = True

    with pytest.raises(ValueError, match="original"):
        _call_reraise(_raise_value_error)


def test_reraise_if_debug_exits_with_code_1_when_debug_false():
    with pytest.raises(typer.Exit) as exc_info:
        _call_reraise(_raise_runtime_error)

    assert exc_info.value.exit_code == 1
