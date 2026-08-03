# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the env module."""

from pathlib import Path
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.env import EnvMetadata, env_get, env_set, get_envs_list, print_env_info


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


def test_render_df_prefix_kept_when_show_prefix():
    meta = EnvMetadata(description="desc")

    result = meta.render("DF_SERVER_PORT", "8080", show_prefix=True)

    assert result.startswith("[cyan bold]DF_SERVER_PORT")


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


@mock.patch("deepfellow.common.env.echo")
def test_env_set_raises_when_file_missing_and_should_raise(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"

    with pytest.raises(typer.Exit):
        env_set(env_file, "DF_FOO", "bar")

    assert mock_echo.error.call_count == 1


def test_env_set_creates_file_when_missing_and_should_not_raise(tmp_path: Path):
    env_file = tmp_path / ".env"

    env_set(env_file, "DF_FOO", "bar", should_raise=False, quiet=True)

    assert env_file.is_file()
    assert "DF_FOO=bar" in env_file.read_text()


@mock.patch("deepfellow.common.env.echo")
def test_env_set_adds_df_prefix_when_missing(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    env_set(env_file, "foo", "bar", quiet=True)

    assert mock_echo.debug.call_count == 1
    assert "DF_FOO=bar" in env_file.read_text()


@mock.patch("deepfellow.common.env.echo")
def test_env_set_does_not_add_df_prefix_when_already_present(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    env_set(env_file, "DF_FOO", "bar", quiet=True)

    assert mock_echo.debug.call_count == 0
    assert "DF_FOO=bar" in env_file.read_text()


def test_env_set_skips_df_prefix_when_disabled(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    env_set(env_file, "foo", "bar", df_prefix=False, quiet=True)

    assert "FOO=bar" in env_file.read_text()
    assert "DF_FOO" not in env_file.read_text()


def test_env_set_preserves_existing_values(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_EXISTING=old\n")

    env_set(env_file, "DF_FOO", "bar", quiet=True)

    content = env_file.read_text()
    assert "DF_EXISTING=old" in content
    assert "DF_FOO=bar" in content


@mock.patch("deepfellow.common.env.save_env_file")
def test_env_set_forwards_quiet_and_kwargs_to_save_env_file(mock_save_env_file: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("")

    env_set(env_file, "DF_FOO", "bar", quiet=True, docker_note=False)

    assert mock_save_env_file.call_count == 1
    assert mock_save_env_file.call_args == mock.call(env_file, {"DF_FOO": "bar"}, quiet=True, docker_note=False)


@mock.patch("deepfellow.common.env.echo")
def test_env_get_raises_when_file_missing_and_should_raise(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"

    with pytest.raises(typer.Exit):
        env_get(env_file, "DF_FOO")

    assert mock_echo.error.call_count == 1


def test_env_get_returns_default_when_file_missing_and_should_not_raise(tmp_path: Path):
    env_file = tmp_path / ".env"

    result = env_get(env_file, "DF_FOO", should_raise=False, default="fallback")

    assert result == "fallback"


def test_env_get_returns_default_when_key_missing_and_file_exists(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_OTHER=val\n")

    result = env_get(env_file, "DF_FOO", default="fallback")

    assert result == "fallback"


@mock.patch("deepfellow.common.env.echo")
def test_env_get_adds_df_prefix_when_missing(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_FOO=bar\n")

    result = env_get(env_file, "foo")

    assert result == "bar"
    assert mock_echo.debug.call_count == 1


@mock.patch("deepfellow.common.env.echo")
def test_env_get_does_not_add_df_prefix_when_already_present(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_FOO=bar\n")

    result = env_get(env_file, "DF_FOO")

    assert result == "bar"
    assert mock_echo.debug.call_count == 0


def test_env_get_skips_df_prefix_when_disabled(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=bar\n")

    result = env_get(env_file, "foo", df_prefix=False)

    assert result == "bar"


def test_env_get_returns_value_when_present(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_FOO=bar\n")

    result = env_get(env_file, "DF_FOO")

    assert result == "bar"


@mock.patch("deepfellow.common.env.echo")
def test_get_envs_list_raises_when_file_missing(mock_echo: Mock, tmp_path: Path):
    env_file = tmp_path / ".env"

    with pytest.raises(typer.Exit):
        get_envs_list(env_file)

    assert mock_echo.error.call_count == 1


def test_get_envs_list_returns_formatted_strings(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text("DF_FOO=bar\nDF_BAZ=qux\n")

    result = get_envs_list(env_file)

    assert result == ["DF_FOO=bar", "DF_BAZ=qux"]
