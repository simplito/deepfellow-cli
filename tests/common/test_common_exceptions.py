# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the exceptions module."""

import inspect
from collections.abc import Callable

import pytest
import typer

from deepfellow.common.exceptions import (
    DockerNetworkError,
    DockerSocketNotFoundError,
    InstallError,
    reraise_if_debug,
    translate_to_install_error,
)
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


def test_translate_to_install_error_wraps_bad_parameter_with_its_message() -> None:
    @translate_to_install_error
    def install() -> None:
        raise typer.BadParameter("Invalid value")

    with pytest.raises(InstallError, match="Invalid value"):
        install()


def test_translate_to_install_error_wraps_exit_with_generic_message() -> None:
    @translate_to_install_error
    def install() -> None:
        raise typer.Exit(1)

    with pytest.raises(InstallError):
        install()


def test_translate_to_install_error_wraps_docker_socket_not_found_error_with_its_message() -> None:
    @translate_to_install_error
    def install() -> None:
        raise DockerSocketNotFoundError("docker.sock not found")

    with pytest.raises(InstallError, match=r"docker\.sock not found"):
        install()


def test_translate_to_install_error_wraps_docker_network_error_with_its_message() -> None:
    @translate_to_install_error
    def install() -> None:
        raise DockerNetworkError("unable to list docker networks")

    with pytest.raises(InstallError, match="unable to list docker networks"):
        install()


def test_translate_to_install_error_wraps_os_error_with_its_message() -> None:
    @translate_to_install_error
    def install() -> None:
        raise OSError("disk full")

    with pytest.raises(InstallError, match="disk full"):
        install()


def test_translate_to_install_error_passes_through_other_exceptions() -> None:
    @translate_to_install_error
    def install() -> None:
        raise ValueError("unrelated")

    with pytest.raises(ValueError, match="unrelated"):
        install()


def test_translate_to_install_error_preserves_signature_and_forwards_arguments() -> None:
    calls = []

    @translate_to_install_error
    def install(directory: str, *, force: bool = False) -> None:
        calls.append((directory, force))

    install("/tmp/dir", force=True)

    assert calls == [("/tmp/dir", True)]
    assert list(inspect.signature(install).parameters) == ["directory", "force"]


def test_translate_to_install_error_propagates_return_value() -> None:
    """Most decorated functions return None, but an ask-phase function (e.g. suite install's
    _infra_config()) returns its resolved config, which its caller needs - this must not be
    silently discarded the way it would be if the wrapper's own body didn't `return` it."""

    @translate_to_install_error
    def resolve() -> dict[str, str]:
        return {"key": "value"}

    assert resolve() == {"key": "value"}


def test_translate_to_install_error_propagates_falsy_return_values() -> None:
    """A naive implementation could accidentally special-case a falsy return (treating it like the
    "no return statement" None every other decorated function relies on) - pin the exact value for
    False, 0, and "" so that never quietly regresses."""

    @translate_to_install_error
    def returns_false() -> bool:
        return False

    @translate_to_install_error
    def returns_zero() -> int:
        return 0

    @translate_to_install_error
    def returns_empty_string() -> str:
        return ""

    assert returns_false() is False
    assert returns_zero() == 0
    assert returns_empty_string() == ""
