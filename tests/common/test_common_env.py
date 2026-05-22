# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the env module."""

from unittest import mock
from unittest.mock import Mock

from deepfellow.common.env import EnvMetadata, print_env_info


def test_render_empty_value_shows_undefined():
    meta = EnvMetadata(description="desc")

    result = meta.render("DF_FOO", "")

    assert "undefined" in result


def test_render_sensitive_value_hidden_by_default():
    meta = EnvMetadata(description="desc", sensitive=True)

    result = meta.render("DF_FOO", "secret123")

    assert "secret123" not in result
    assert "*****" in result


def test_render_sensitive_value_shown_with_show_secret():
    meta = EnvMetadata(description="desc", sensitive=True)

    result = meta.render("DF_FOO", "secret123", show_secret=True)

    assert "secret123" in result


def test_render_normal_value_shown():
    meta = EnvMetadata(description="desc")

    result = meta.render("DF_FOO", "hello")

    assert "hello" in result


def test_render_df_prefix_stripped_from_key():
    meta = EnvMetadata(description="desc")

    result = meta.render("DF_SERVER_PORT", "8080")

    assert "SERVER_PORT" in result
    assert result.startswith("[cyan bold]SERVER_PORT")


def test_render_key_without_df_prefix_unchanged():
    meta = EnvMetadata(description="desc")

    result = meta.render("MY_VAR", "val")

    assert "MY_VAR" in result


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_doc_calls_echo_info_with_doc_header(mock_echo: Mock):
    metadata = {"DF_FOO": EnvMetadata(description="Foo desc")}

    print_env_info("My header", metadata, {}, doc=True)

    called_msg = mock_echo.info.call_args[0][0]
    assert called_msg.startswith("Environment variables documentation:")


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_doc_includes_rendered_key_and_description(mock_echo: Mock):
    metadata = {"DF_BAR": EnvMetadata(description="Bar desc")}

    print_env_info("Header", metadata, {"DF_BAR": "val"}, doc=True)

    called_msg = mock_echo.info.call_args[0][0]
    assert "BAR" in called_msg
    assert "val" in called_msg
    assert "Bar desc" in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_doc_missing_env_value_treated_as_empty(mock_echo: Mock):
    metadata = {"DF_MISSING": EnvMetadata(description="desc")}

    print_env_info("Header", metadata, {}, doc=True)

    called_msg = mock_echo.info.call_args[0][0]
    assert "undefined" in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_doc_show_secret_reveals_sensitive_value(mock_echo: Mock):
    metadata = {"DF_SECRET": EnvMetadata(description="desc", sensitive=True)}

    print_env_info("Header", metadata, {"DF_SECRET": "pass123"}, show_secret=True, doc=True)

    called_msg = mock_echo.info.call_args[0][0]
    assert "pass123" in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_doc_sensitive_hidden_without_show_secret(mock_echo: Mock):
    metadata = {"DF_SECRET": EnvMetadata(description="desc", sensitive=True)}

    print_env_info("Header", metadata, {"DF_SECRET": "pass123"}, show_secret=False, doc=True)

    called_msg = mock_echo.info.call_args[0][0]
    assert "pass123" not in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_normal_uses_given_header(mock_echo: Mock):
    metadata = {"DF_FOO": EnvMetadata(description="desc")}

    print_env_info("My header", metadata, {"DF_FOO": "val"}, doc=False)

    called_msg = mock_echo.info.call_args[0][0]
    assert called_msg.startswith("My header")


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_normal_renders_env_values(mock_echo: Mock):
    metadata = {"DF_A": EnvMetadata(description="A desc"), "DF_B": EnvMetadata(description="B desc")}

    print_env_info("Header", metadata, {"DF_A": "alpha", "DF_B": "beta"}, doc=False)

    called_msg = mock_echo.info.call_args[0][0]
    assert "alpha" in called_msg
    assert "beta" in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_normal_unknown_key_uses_default_metadata(mock_echo: Mock):
    metadata: dict = {}

    print_env_info("Header", metadata, {"DF_UNKNOWN": "val"}, doc=False)

    called_msg = mock_echo.info.call_args[0][0]
    assert "val" in called_msg


@mock.patch("deepfellow.common.env.echo")
def test_print_env_info_echo_called_once_regardless_of_mode(mock_echo: Mock):
    metadata = {"DF_X": EnvMetadata(description="desc")}

    print_env_info("Header", metadata, {}, doc=True)
    print_env_info("Header", metadata, {}, doc=False)

    assert mock_echo.info.call_count == 2
