# DeepFellow Software Framework.
# Copyright © 2025 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock, call, patch

import pytest
import typer

from deepfellow.common.config import (
    configure_uuid_key,
    dict_to_env,
    env_to_dict,
    get_config_path,
    load_config,
    read_env_file,
    save_env_file,
    store_config,
)


@pytest.fixture
def temp_config_file(tmp_path):
    config_data = {"database": {"host": "localhost", "port": 5432}, "api": {"debug": True}}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    return config_file


@pytest.fixture
def temp_invalid_json_file(tmp_path):
    config_file = tmp_path / "invalid.json"
    config_file.write_text('{"invalid": json}', encoding="utf-8")
    return config_file


@pytest.fixture
def temp_invalid_encoding_file(tmp_path):
    config_file = tmp_path / "invalid_encoding.json"
    config_file.write_bytes(b'\xff\xfe{"test": "value"}')  # Invalid UTF-8
    return config_file


@patch("deepfellow.common.config.click")
def test_get_config_path_with_path_object(mock_click: Mock, context, tmp_path):
    config_file = tmp_path / "config.json"
    context.obj = {"config-path": config_file}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == config_file
    assert isinstance(result, Path)
    assert result is config_file  # Should be the exact same object


@patch("deepfellow.common.config.click")
def test_get_config_path_with_string_path(mock_click: Mock, context, tmp_path):
    config_file = tmp_path / "config.json"
    context.obj = {"config-path": str(config_file)}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == config_file
    assert isinstance(result, Path)
    assert result is not config_file  # Shouldn't be the exact same object


@pytest.mark.parametrize(
    "invalid_context_obj",
    [None, {}, {"other_key": "value"}, {"config": None}, {"config": ""}, {"config": False}],
)
@patch("deepfellow.common.config.click")
def test_get_config_path_invalid_context_obj(mock_click: Mock, invalid_context_obj: dict | None, context):
    context.obj = invalid_context_obj
    mock_click.get_current_context.return_value = context

    with pytest.raises(typer.BadParameter, match="No config provided."):
        get_config_path()


@patch("deepfellow.common.config.click")
def test_get_config_path_relative_string_path(mock_click: Mock, context):
    context.obj = {"config-path": "config.json"}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == Path("config.json")


@pytest.mark.parametrize(
    "valid_path",
    ["config.json", "~/config.json", "C:\\Users\\user\\config.json", "/path/with spaces/and-dashes/config_file.json"],
)
@patch("deepfellow.common.config.click")
def test_get_config_path_valid_path(mock_click: Mock, valid_path, context):
    context.obj = {"config-path": valid_path}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == Path(valid_path)


@patch("deepfellow.common.config.click")
def test_get_config_path_preserves_path_properties(mock_click: Mock, context, tmp_path):
    config_file = tmp_path / "subdir" / "config.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text('{"test": "value"}')
    context.obj = {"config-path": str(config_file)}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == config_file
    assert result.name == "config.json"
    assert result.suffix == ".json"
    assert result.parent.name == "subdir"


@patch("deepfellow.common.config.click")
def test_get_config_path_with_additional_context_data(mock_click: Mock, context, tmp_path):
    config_file = tmp_path / "config.json"
    context.obj = {"config-path": config_file, "verbose": True, "dry_run": False, "other_data": {"nested": "value"}}
    mock_click.get_current_context.return_value = context

    result = get_config_path()

    assert result == config_file
    assert isinstance(result, Path)


@patch("deepfellow.common.config.get_config_path")
def test_load_config_success(mock_get_config_path, temp_config_file):
    mock_get_config_path.return_value = temp_config_file

    result = load_config()

    expected = {"database": {"host": "localhost", "port": 5432}, "api": {"debug": True}}
    assert result == expected


@patch("deepfellow.common.config.get_config_path")
def test_load_config_empty_file(mock_get_config_path, tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding="utf-8")
    mock_get_config_path.return_value = empty_file

    result = load_config()

    assert result == {}


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_file_not_found(mock_get_config_path, mock_echo, tmp_path):
    nonexistent_file = tmp_path / "nonexistent.json"
    mock_get_config_path.return_value = nonexistent_file

    with pytest.raises(FileNotFoundError):
        load_config(raise_on_error=True)

    assert mock_echo.error.call_count == 1
    assert "Config file not found:" in mock_echo.error.call_args[0][0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_file_not_found_without_raise_on_error(mock_get_config_path, mock_echo, tmp_path):
    empty_file = tmp_path / "empty.json"
    mock_get_config_path.return_value = empty_file

    result = load_config()

    assert result == {}
    assert mock_echo.error.call_count == 0


@patch.object(Path, "read_text", side_effect=PermissionError("Access denied"))
@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_permission_error(mock_get_config_path, mock_echo, mock_read_text, context, temp_config_file):
    mock_get_config_path.return_value = temp_config_file

    with pytest.raises(typer.Exit) as exc_info:
        load_config(raise_on_error=True)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == call(f"Permission denied reading config file: {temp_config_file}")


@patch.object(Path, "read_text", side_effect=PermissionError("Access denied"))
@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_permission_error_no_raise_on_error(
    mock_get_config_path, mock_echo, mock_read_text, context, temp_config_file
):
    mock_get_config_path.return_value = temp_config_file

    result = load_config()

    assert result == {}
    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == call(f"Permission denied reading config file: {temp_config_file}")


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_json_decode_error(mock_get_config_path, mock_echo, temp_invalid_json_file):
    mock_get_config_path.return_value = temp_invalid_json_file

    with pytest.raises(typer.Exit) as exc_info:
        load_config(raise_on_error=True)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Error parsing config file" in call_args[0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_json_decode_error_no_raise_on_error(mock_get_config_path, mock_echo, temp_invalid_json_file):
    mock_get_config_path.return_value = temp_invalid_json_file

    result = load_config()

    assert result == {}
    assert mock_echo.error.call_count == 1
    assert "Error parsing config file" in mock_echo.error.call_args[0][0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_unicode_decode_error(mock_get_config_path, mock_echo, temp_invalid_encoding_file):
    mock_get_config_path.return_value = temp_invalid_encoding_file

    with pytest.raises(typer.Exit) as exc_info:
        load_config(raise_on_error=True)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Error reading config file (encoding issue)" in call_args[0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_unicode_decode_error_no_raise_on_error(
    mock_get_config_path, mock_echo, temp_invalid_encoding_file
):
    mock_get_config_path.return_value = temp_invalid_encoding_file

    result = load_config()

    assert result == {}
    assert mock_echo.error.call_count == 1
    assert "Error reading config file (encoding issue)" in mock_echo.error.call_args[0][0]


@patch("deepfellow.common.config.get_config_path")
def test_load_config_complex_json(mock_get_config_path, tmp_path):
    complex_config = {
        "database": {
            "connections": {"primary": {"host": "db1", "port": 5432}, "secondary": {"host": "db2", "port": 5433}},
            "pool_size": 20,
        },
        "features": {"enabled": ["auth", "logging", "metrics"], "disabled": ["debug"]},
        "version": "1.0.0",
    }

    config_file = tmp_path / "complex.json"
    config_file.write_text(json.dumps(complex_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config()

    assert result == complex_config
    assert result["database"]["connections"]["primary"]["host"] == "db1"
    assert "auth" in result["features"]["enabled"]


@patch("deepfellow.common.config.get_config_path")
def test_load_config_with_unicode_content(mock_get_config_path, tmp_path):
    unicode_config = {"app_name": "My App™", "description": "ćśńół", "emoji": "🚀"}
    config_file = tmp_path / "unicode.json"
    config_file.write_text(json.dumps(unicode_config, ensure_ascii=False), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config()

    assert result == unicode_config
    assert result["app_name"] == "My App™"
    assert result["description"] == "ćśńół"
    assert result["emoji"] == "🚀"


@patch("deepfellow.common.config.get_config_path")
def test_load_config_json_with_null_values(mock_get_config_path, tmp_path):
    config_with_nulls = {"database": {"host": "localhost", "password": None, "ssl": False}, "optional_feature": None}
    config_file = tmp_path / "nulls.json"
    config_file.write_text(json.dumps(config_with_nulls), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config()

    assert result == config_with_nulls
    assert result["database"]["password"] is None
    assert result["optional_feature"] is None
    assert result["database"]["ssl"] is False


@patch("deepfellow.common.config.get_config_path")
def test_load_config_large_file(mock_get_config_path, tmp_path):
    large_config = {
        "services": {f"service_{i}": {"port": 8000 + i, "enabled": i % 2 == 0} for i in range(100)},
        "metadata": {"version": "2.0.0", "created_by": "test_suite"},
    }
    config_file = tmp_path / "large.json"
    config_file.write_text(json.dumps(large_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config()

    assert result == large_config
    assert len(result["services"]) == 100
    assert result["services"]["service_0"]["enabled"] is True
    assert result["services"]["service_1"]["enabled"] is False


@patch("deepfellow.common.config.get_config_path")
def test_load_config_nested_directories(mock_get_config_path, tmp_path):
    config_dir = tmp_path / "configs" / "environments"
    config_dir.mkdir(parents=True)
    config_data = {"environment": "test", "nested": True}
    config_file = config_dir / "test.json"
    config_file.write_text(json.dumps(config_data), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config()

    assert result == config_data
    assert result["environment"] == "test"
    assert result["nested"] is True


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_create_new_file(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "new_config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"database": {"host": "localhost"}, "debug": True}

    store_config(config_data)

    assert config_file.exists()
    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert mock_echo.info.call_count == 1
    call_args = mock_echo.info.call_args[0]
    assert f"Config saved to: {config_file}" in call_args[0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_update_existing_file(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "existing_config.json"
    existing_config = {"database": {"host": "old_host"}, "api": {"port": 8000}}
    config_file.write_text(json.dumps(existing_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file
    new_config = {"database": {"host": "new_host"}, "debug": True}

    store_config(new_config, update=True)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    expected = {
        "database": {"host": "new_host"},  # Updated
        "api": {"port": 8000},  # Preserved
        "debug": True,  # Added
    }
    assert saved_content == expected
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_no_update(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "existing_config.json"
    existing_config = {"database": {"host": "old_host"}, "api": {"port": 8000}}
    config_file.write_text(json.dumps(existing_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file
    new_config = {"database": {"host": "new_host"}, "debug": True}

    store_config(new_config, update=False)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == new_config
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_create_parent_directories(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "deep" / "nested" / "config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"test": "value"}

    store_config(config_data)

    assert config_file.parent.exists()
    assert config_file.exists()
    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_pretty_formatting(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"database": {"host": "localhost", "port": 5432}, "api": {"debug": True}}

    store_config(config_data)

    content = config_file.read_text(encoding="utf-8")
    assert "  " in content  # Should have 2-space indentation
    assert content.count("\n") > 1  # Should be multi-line
    parsed = json.loads(content)
    assert parsed == config_data
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_unicode_content(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "unicode_config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"app_name": "My App™", "description": "ćśńół", "emoji": "🚀"}

    store_config(config_data)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert saved_content["app_name"] == "My App™"
    assert saved_content["description"] == "ćśńół"
    assert saved_content["emoji"] == "🚀"
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_deep_copy_modification(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "config.json"
    existing_config = {"existing": "value"}
    config_file.write_text(json.dumps(existing_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file
    original_data = {"new": "value"}
    original_copy = deepcopy(original_data)

    store_config(original_data, update=True)

    assert original_data == original_copy
    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == {"existing": "value", "new": "value"}
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_update_nonexistent_file(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "nonexistent.json"
    mock_get_config_path.return_value = config_file
    config_data = {"new": "config"}

    store_config(config_data, update=True)

    assert config_file.exists()
    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert mock_echo.info.call_count == 1


@patch.object(Path, "write_text", side_effect=PermissionError("Access denied"))
@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_permission_error(mock_get_config_path, mock_echo, mock_write_text, tmp_path):
    config_file = tmp_path / "config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"test": "value"}

    with pytest.raises(typer.Exit) as exc_info:
        store_config(config_data)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Permission denied writing config file" in call_args[0]
    assert str(config_file) in call_args[0]


@patch.object(Path, "write_text", side_effect=OSError("Disk full"))
@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_os_error(mock_get_config_path, mock_echo, mock_write_text, tmp_path):
    config_file = tmp_path / "config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"test": "value"}

    with pytest.raises(typer.Exit) as exc_info:
        store_config(config_data)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Error writing config file" in call_args[0]
    assert "Disk full" in call_args[0]


@patch.object(Path, "mkdir", side_effect=PermissionError("Cannot create directory"))
@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_mkdir_permission_error(mock_get_config_path, mock_echo, mock_mkdir, tmp_path):
    config_file = tmp_path / "restricted" / "config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"test": "value"}

    with pytest.raises(typer.Exit) as exc_info:
        store_config(config_data)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Permission denied writing config file" in call_args[0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_complex_nested_data(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "complex_config.json"
    mock_get_config_path.return_value = config_file
    config_data = {
        "database": {
            "connections": {"primary": {"host": "db1", "port": 5432}, "secondary": {"host": "db2", "port": 5433}},
            "pool_size": 20,
        },
        "features": {"enabled": ["auth", "logging"], "disabled": ["debug"]},
        "metadata": {"version": "1.0.0", "created_at": "2024-01-01"},
    }

    store_config(config_data)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert saved_content["database"]["connections"]["primary"]["host"] == "db1"
    assert "auth" in saved_content["features"]["enabled"]
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_merge_preserves_nested_structure(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "nested_config.json"
    existing_config = {"database": {"host": "old_host", "port": 5432}, "api": {"port": 8000, "debug": False}}
    config_file.write_text(json.dumps(existing_config), encoding="utf-8")
    mock_get_config_path.return_value = config_file
    new_config = {
        "database": {"host": "new_host"},  # Should replace entire database section
        "logging": {"level": "INFO"},  # Should add new section
    }

    store_config(new_config, update=True)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    expected = {
        "database": {"host": "new_host"},  # Completely replaced
        "api": {"port": 8000, "debug": False},  # Preserved
        "logging": {"level": "INFO"},  # Added
    }
    assert saved_content == expected
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_empty_dict(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "empty_config.json"
    mock_get_config_path.return_value = config_file
    config_data = {}

    store_config(config_data)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == {}
    assert mock_echo.info.call_count == 1


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_store_config_with_none_values(mock_get_config_path, mock_echo, tmp_path):
    config_file = tmp_path / "null_config.json"
    mock_get_config_path.return_value = config_file
    config_data = {"database": {"password": None}, "optional_feature": None, "enabled": False}

    store_config(config_data)

    saved_content = json.loads(config_file.read_text(encoding="utf-8"))
    assert saved_content == config_data
    assert saved_content["database"]["password"] is None
    assert saved_content["optional_feature"] is None
    assert saved_content["enabled"] is False
    assert mock_echo.info.call_count == 1


@pytest.mark.parametrize(
    ("data", "prefix", "expected"),
    [
        ({"key1": "value1", "key2": "value2"}, "DF_", {"DF_KEY1": "value1", "DF_KEY2": "value2"}),
        ({"key": "value"}, "CUSTOM_", {"CUSTOM_KEY": "value"}),
        ({"key": "value"}, "", {"KEY": "value"}),
        ({"key": "value"}, None, {"KEY": "value"}),
    ],
)
def test_dict_to_env_prefix_handling(data: dict[str, Any], prefix: str, expected: dict[str, str]):
    result = dict_to_env(data, prefix=prefix)

    assert result == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"parent": {"child1": "value1", "child2": "value2"}},
            {"DF_PARENT__CHILD1": "value1", "DF_PARENT__CHILD2": "value2"},
        ),
        ({"level1": {"level2": {"level3": "deep_value"}}}, {"DF_LEVEL1__LEVEL2__LEVEL3": "deep_value"}),
        ({"database": {"credentials": {"username": "admin"}}}, {"DF_DATABASE__CREDENTIALS__USERNAME": "admin"}),
    ],
)
def test_dict_to_env_nested_structures(data: dict[str, Any], expected: dict[str, str]):
    result = dict_to_env(data)

    assert result == expected


@pytest.mark.parametrize(
    ("value", "expected_str"),
    [
        (42, "42"),
        (3.14, "3.14"),
        (True, "True"),
        (None, "None"),
        (False, "False"),
        (0, "0"),
    ],
)
def test_dict_to_env_value_conversion(value: Any, expected_str: str):
    data = {"key": value}

    result = dict_to_env(data)

    expected = {"DF_KEY": expected_str}
    assert result == expected


@pytest.mark.parametrize(
    ("key", "expected_key"),
    [
        ("MixedCase", "DF_MIXEDCASE"),
        ("lowercase", "DF_LOWERCASE"),
        ("UPPERCASE", "DF_UPPERCASE"),
        ("snake_case", "DF_SNAKE_CASE"),
    ],
)
def test_dict_to_env_case_handling(key: str, expected_key: str):
    data = {key: "value"}

    result = dict_to_env(data)

    expected = {expected_key: "value"}
    assert result == expected


def test_dict_to_env_mixed_nested_and_flat():
    data = {"flat_key": "flat_value", "nested": {"child": "nested_value"}, "another_flat": 123}

    result = dict_to_env(data)

    expected = {"DF_FLAT_KEY": "flat_value", "DF_NESTED__CHILD": "nested_value", "DF_ANOTHER_FLAT": "123"}
    assert result == expected


def test_dict_to_env_empty_dict():
    data: dict[str, Any] = {}

    result = dict_to_env(data)

    expected: dict[str, str] = {}
    assert result == expected


def test_dict_to_env_nested_empty_dict():
    data = {"parent": {}}

    result = dict_to_env(data)

    expected: dict[str, str] = {}
    assert result == expected


def test_dict_to_env_complex_nested_structure():
    data = {
        "database": {"host": "localhost", "port": 5432, "credentials": {"username": "admin", "password": "secret"}},
        "cache": {"redis": {"url": "redis://localhost"}},
    }

    result = dict_to_env(data)

    expected = {
        "DF_DATABASE__HOST": "localhost",
        "DF_DATABASE__PORT": "5432",
        "DF_DATABASE__CREDENTIALS__USERNAME": "admin",
        "DF_DATABASE__CREDENTIALS__PASSWORD": "secret",
        "DF_CACHE__REDIS__URL": "redis://localhost",
    }
    assert result == expected


def test_dict_to_env_parent_key_parameter():
    data = {"child": "value"}

    result = dict_to_env(data, prefix="", parent_key="PARENT")

    expected = {"PARENT__CHILD": "value"}
    assert result == expected


def test_dict_to_env_parent_key_with_nested():
    data = {"child": {"grandchild": "value"}}

    result = dict_to_env(data, prefix="", parent_key="PARENT")

    expected = {"PARENT__CHILD__GRANDCHILD": "value"}
    assert result == expected


def test_env_to_dict_simple_flat_vars():
    env_vars = {"KEY1": "value1", "KEY2": "value2"}

    result = env_to_dict(env_vars)

    expected = {"key1": "value1", "key2": "value2"}
    assert result == expected


def test_env_to_dict_nested_vars():
    env_vars = {"PARENT__CHILD1": "value1", "PARENT__CHILD2": "value2"}

    result = env_to_dict(env_vars)

    expected = {"parent": {"child1": "value1", "child2": "value2"}}
    assert result == expected


def test_env_to_dict_deeply_nested_vars():
    env_vars = {"LEVEL1__LEVEL2__LEVEL3": "deep_value"}

    result = env_to_dict(env_vars)

    expected = {"level1": {"level2": {"level3": "deep_value"}}}
    assert result == expected


def test_env_to_dict_mixed_nested_and_flat():
    env_vars = {"FLAT_KEY": "flat_value", "NESTED__CHILD": "nested_value", "ANOTHER_FLAT": "123"}

    result = env_to_dict(env_vars)

    expected = {"flat_key": "flat_value", "nested": {"child": "nested_value"}, "another_flat": 123}
    assert result == expected


def test_env_to_dict_with_prefix():
    env_vars = {"DF_KEY1": "value1", "DF_KEY2": "value2", "OTHER_KEY": "should_be_ignored"}

    result = env_to_dict(env_vars, prefix="DF_")

    expected = {"key1": "value1", "key2": "value2"}
    assert result == expected


def test_env_to_dict_nested_with_prefix():
    env_vars = {"DF_PARENT__CHILD": "value", "OTHER_PARENT__CHILD": "ignored"}

    result = env_to_dict(env_vars, prefix="DF_")

    expected = {"parent": {"child": "value"}}
    assert result == expected


def test_env_to_dict_empty_prefix():
    env_vars = {"KEY": "value"}

    result = env_to_dict(env_vars, prefix="")

    expected = {"key": "value"}
    assert result == expected


def test_env_to_dict_integer_conversion():
    env_vars = {"INT_VAL": "42", "ZERO_VAL": "0", "NEGATIVE_INT": "-123"}

    result = env_to_dict(env_vars)

    expected = {
        "int_val": 42,
        "zero_val": 0,
        "negative_int": "-123",  # Negative numbers don't match isdigit()
    }
    assert result == expected


def test_env_to_dict_boolean_conversion():
    env_vars = {
        "BOOL_TRUE_LOWER": "true",
        "BOOL_TRUE_UPPER": "TRUE",
        "BOOL_TRUE_MIXED": "True",
        "BOOL_FALSE_LOWER": "false",
        "BOOL_FALSE_UPPER": "FALSE",
        "BOOL_FALSE_MIXED": "False",
    }

    result = env_to_dict(env_vars)

    expected = {
        "bool_true_lower": True,
        "bool_true_upper": True,
        "bool_true_mixed": True,
        "bool_false_lower": False,
        "bool_false_upper": False,
        "bool_false_mixed": False,
    }
    assert result == expected


def test_env_to_dict_mixed_types():
    env_vars = {
        "STRING_VAL": "hello",
        "INT_VAL": "42",
        "BOOL_VAL": "true",
        "FLOAT_VAL": "3.14",  # Should remain string since not isdigit()
    }

    result = env_to_dict(env_vars)

    expected = {"string_val": "hello", "int_val": 42, "bool_val": True, "float_val": "3.14"}
    assert result == expected


def test_env_to_dict_empty_env_vars():
    env_vars: dict[str, str] = {}

    result = env_to_dict(env_vars)

    expected: dict[str, Any] = {}
    assert result == expected


def test_env_to_dict_no_matching_prefix():
    env_vars = {"OTHER_KEY": "value"}

    result = env_to_dict(env_vars, prefix="DF_")

    expected: dict[str, Any] = {}
    assert result == expected


def test_env_to_dict_case_conversion():
    env_vars = {"MIXEDCASE__SUBKEY": "value"}

    result = env_to_dict(env_vars)

    expected = {"mixedcase": {"subkey": "value"}}
    assert result == expected


def test_env_to_dict_complex_nested_structure():
    env_vars = {
        "DF_DATABASE__HOST": "localhost",
        "DF_DATABASE__PORT": "5432",
        "DF_DATABASE__CREDENTIALS__USERNAME": "admin",
        "DF_DATABASE__CREDENTIALS__PASSWORD": "secret",
        "DF_CACHE__REDIS__URL": "redis://localhost",
        "DF_DEBUG": "true",
    }

    result = env_to_dict(env_vars, prefix="DF_")

    expected = {
        "database": {"host": "localhost", "port": 5432, "credentials": {"username": "admin", "password": "secret"}},
        "cache": {"redis": {"url": "redis://localhost"}},
        "debug": True,
    }
    assert result == expected


@pytest.mark.parametrize(
    ("env_key", "env_value", "expected_key", "expected_value"),
    [
        ("EMPTY_STRING", "", "empty_string", ""),
        ("SPACE_STRING", " ", "space_string", " "),
        ("NUMERIC_STRING", "007", "numeric_string", 7),
        ("BOOL_LIKE", "yes", "bool_like", "yes"),
        ("SINGLE_UNDERSCORE", "value", "single_underscore", "value"),
    ],
)
def test_env_to_dict_special_values(env_key: str, env_value: str, expected_key: str, expected_value: str):
    env_vars = {env_key: env_value}

    result = env_to_dict(env_vars)

    expected = {expected_key: expected_value}
    assert result == expected


def test_env_to_dict_partial_prefix_match():
    env_vars = {
        "DF_KEY": "included",
        "DFX_KEY": "excluded",  # Partial match should be excluded
        "XDF_KEY": "excluded",  # Partial match should be excluded
    }

    result = env_to_dict(env_vars, prefix="DF_")

    expected = {"key": "included"}
    assert result == expected


def test_env_to_dict_overwrite_intermediate_keys():
    env_vars = {"PARENT__CHILD": "child_value", "PARENT": "parent_value"}

    result = env_to_dict(env_vars)

    # The function should handle this case - parent gets overwritten
    expected = {"parent": "parent_value"}
    assert result == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("KEY=value", {"KEY": "value"}),
        ("KEY1=value1\nKEY2=value2", {"KEY1": "value1", "KEY2": "value2"}),
        ("KEY_WITH_UNDERSCORE=value", {"KEY_WITH_UNDERSCORE": "value"}),
        ("KEY123=value", {"KEY123": "value"}),
        ("_PRIVATE_KEY=value", {"_PRIVATE_KEY": "value"}),
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_basic_parsing(mock_path_class: mock.Mock, content: str, expected: dict[str, str]) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == expected
    assert mock_path.exists.call_count == 1
    assert mock_path.read_text.call_count == 1
    assert mock_path.read_text.call_args == mock.call(encoding="utf-8")


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('KEY="quoted value"', {"KEY": "quoted value"}),
        ("KEY='single quoted'", {"KEY": "single quoted"}),
        ('KEY="value with spaces"', {"KEY": "value with spaces"}),
        ("KEY='value with spaces'", {"KEY": "value with spaces"}),
        ('KEY=""', {"KEY": ""}),
        ("KEY=''", {"KEY": ""}),
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_quoted_values(mock_path_class: mock.Mock, content: str, expected: dict[str, str]) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('KEY="line1\\nline2"', {"KEY": "line1\nline2"}),
        ('KEY="tab\\ttab"', {"KEY": "tab\ttab"}),
        ('KEY="quote\\"quote"', {"KEY": 'quote"quote'}),
        ('KEY="backslash\\\\"', {"KEY": "backslash\\"}),
        ('KEY="combo\\n\\t\\""', {"KEY": 'combo\n\t"'}),
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_escape_sequences(mock_path_class: mock.Mock, content: str, expected: dict[str, str]) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("KEY = value", {"KEY": "value"}),
        ("KEY= value", {"KEY": "value"}),
        ("KEY =value", {"KEY": "value"}),
        ("KEY  =  value  ", {"KEY": "value"}),  # Trailing spaces ignored
        ("  KEY=value  ", {"KEY": "value"}),  # Leading/trailing line spaces ignored
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_whitespace_handling(mock_path_class: mock.Mock, content: str, expected: dict[str, str]) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == expected


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("", {}),
        ("\n\n", {}),
        ("# Comment only", {}),
        ("KEY=value\n# Comment", {"KEY": "value"}),
        ("# Comment\nKEY=value", {"KEY": "value"}),
        ("KEY1=value1\n# Comment\nKEY2=value2", {"KEY1": "value1", "KEY2": "value2"}),
        ("  # Indented comment", {}),
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_comments_and_empty_lines(
    mock_path_class: mock.Mock, content: str, expected: dict[str, str]
) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == expected


@pytest.mark.parametrize(
    ("content"),
    [
        ("invalid line without equals"),
        ("123INVALID=value"),  # Key starts with number
        ("INVALID-KEY=value"),  # Key contains dash
        ("=value"),  # Missing key
    ],
)
@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_malformed_lines_skipped(mock_path_class: mock.Mock, content: str) -> None:
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    assert result == {}


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_string_path(mock_path_class: mock.Mock) -> None:
    file_path = "/fake/path/.env"
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = "KEY=value"
    mock_path_class.return_value = mock_path

    result = read_env_file(file_path)

    assert result == {"KEY": "value"}
    assert mock_path_class.call_count == 1
    assert mock_path_class.call_args == mock.call(file_path)


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_path_object(mock_path_class: mock.Mock) -> None:
    file_path = Path("/fake/path/.env")
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = "KEY=value"
    mock_path_class.return_value = mock_path

    result = read_env_file(file_path)

    assert result == {"KEY": "value"}
    assert mock_path_class.call_count == 1
    assert mock_path_class.call_args == mock.call(file_path)


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_file_not_found(mock_path_class: mock.Mock) -> None:
    file_path = "/nonexistent/path/.env"
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = False
    mock_path_class.return_value = mock_path

    with pytest.raises(FileNotFoundError) as exc_info:
        read_env_file(file_path)

    assert "Environment file not found" in str(exc_info.value)
    assert mock_path.exists.call_count == 1
    assert mock_path.read_text.call_count == 0


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_complex_real_world_example(mock_path_class: mock.Mock) -> None:
    content = """
# Database configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME="my_app_db"
DB_USER='admin'
DB_PASSWORD="super\\\"secret\\npassword"

# API settings
API_KEY=abc123def456
DEBUG=true
LOG_LEVEL=INFO

# URLs with special chars
REDIS_URL="redis://localhost:6379/0"

# Empty value
OPTIONAL_SETTING=

# Malformed lines (should be skipped)
INVALID LINE
123STARTS_WITH_NUMBER=value
KEY-WITH-DASH=value

# More config
MAX_CONNECTIONS=100
TIMEOUT="30"
"""
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    expected = {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "my_app_db",
        "DB_USER": "admin",
        "DB_PASSWORD": 'super"secret\npassword',
        "API_KEY": "abc123def456",
        "DEBUG": "true",
        "LOG_LEVEL": "INFO",
        "REDIS_URL": "redis://localhost:6379/0",
        "OPTIONAL_SETTING": "",
        "MAX_CONNECTIONS": "100",
        "TIMEOUT": "30",
    }
    assert result == expected


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_single_quotes_no_escape_processing(mock_path_class: mock.Mock) -> None:
    content = "KEY='value\\nwith\\tescapes'"
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    expected = {"KEY": "value\\nwith\\tescapes"}
    assert result == expected


@mock.patch("deepfellow.common.config.Path")
def test_read_env_file_mixed_quote_types(mock_path_class: mock.Mock) -> None:
    content = """KEY1="double quotes"
KEY2='single quotes'
KEY3=unquoted
KEY4="mixed 'quotes' inside"
KEY5='mixed "quotes" inside'
"""
    mock_path = mock.Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = content
    mock_path_class.return_value = mock_path

    result = read_env_file("/fake/path/.env")

    expected = {
        "KEY1": "double quotes",
        "KEY2": "single quotes",
        "KEY3": "unquoted",
        "KEY4": "mixed 'quotes' inside",
        "KEY5": 'mixed "quotes" inside',
    }
    assert result == expected


@pytest.mark.parametrize(
    ("values", "expected_content"),
    [
        ({"KEY": "value"}, "# Docker Compose Environment Variables\n# Edit these values as needed\n\nKEY=value\n"),
        (
            {"KEY1": "value1", "KEY2": "value2"},
            "# Docker Compose Environment Variables\n# Edit these values as needed\n\nKEY1=value1\nKEY2=value2\n",
        ),
        (
            {"INT_VAL": 42, "STR_VAL": "text"},
            "# Docker Compose Environment Variables\n# Edit these values as needed\n\nINT_VAL=42\nSTR_VAL=text\n",
        ),
        ({}, "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"),
    ],
)
@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_new_file(
    mock_read_env_file: mock.Mock, mock_echo: mock.Mock, values: Mapping[str, str | int], expected_content: str
) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = False
    mock_env_file.as_posix.return_value = "/fake/path/.env"

    save_env_file(mock_env_file, values)

    assert mock_env_file.exists.call_count == 1
    assert mock_read_env_file.call_count == 0
    assert mock_env_file.write_text.call_count == 1
    assert mock_env_file.write_text.call_args == mock.call(expected_content)
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("Generated /fake/path/.env.")


@pytest.mark.parametrize(
    ("existing_vars", "new_values", "expected_content"),
    [
        (
            {"OLD_KEY": "old_value"},
            {"NEW_KEY": "new_value"},
            "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
            "OLD_KEY=old_value\nNEW_KEY=new_value\n",
        ),
        (
            {"KEY": "old_value"},
            {"KEY": "new_value"},
            "# Docker Compose Environment Variables\n# Edit these values as needed\n\nKEY=new_value\n",
        ),
        (
            {"KEY1": "value1", "KEY2": "value2"},
            {"KEY2": "updated", "KEY3": "new"},
            (
                "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
                "KEY1=value1\nKEY2=updated\nKEY3=new\n"
            ),
        ),
        (
            {"EXISTING": "value"},
            {},
            "# Docker Compose Environment Variables\n# Edit these values as needed\n\nEXISTING=value\n",
        ),
    ],
)
@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_existing_file_merge(
    mock_read_env_file: mock.Mock,
    mock_echo: mock.Mock,
    existing_vars: dict[str, str],
    new_values: Mapping[str, str | int],
    expected_content: str,
) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = True
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    mock_read_env_file.return_value = existing_vars

    save_env_file(mock_env_file, new_values)

    assert mock_env_file.exists.call_count == 1
    assert mock_read_env_file.call_count == 1
    assert mock_read_env_file.call_args == mock.call(mock_env_file)
    assert mock_env_file.write_text.call_count == 1
    assert mock_env_file.write_text.call_args == mock.call(expected_content)
    assert mock_echo.info.call_count == 1
    assert mock_echo.info.call_args == mock.call("Updated /fake/path/.env.")


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_new_values_take_precedence(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = True
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    mock_read_env_file.return_value = {"SAME_KEY": "old_value", "OTHER_KEY": "keep_this"}
    new_values = {"SAME_KEY": "new_value", "ANOTHER_KEY": "add_this"}

    save_env_file(mock_env_file, new_values)

    expected_content = (
        "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
        "SAME_KEY=new_value\nOTHER_KEY=keep_this\nANOTHER_KEY=add_this\n"
    )
    assert mock_env_file.write_text.call_args == mock.call(expected_content)


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_empty_existing_file(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = True
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    mock_read_env_file.return_value = {}
    new_values = {"KEY": "value"}

    save_env_file(mock_env_file, new_values)

    expected_content = "# Docker Compose Environment Variables\n# Edit these values as needed\n\nKEY=value\n"
    assert mock_read_env_file.call_count == 1
    assert mock_env_file.write_text.call_args == mock.call(expected_content)
    assert mock_echo.info.call_args == mock.call("Updated /fake/path/.env.")


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_mixed_value_types(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = False
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    values: dict[str, str | int] = {"STRING_VAL": "text", "INT_VAL": 42, "ZERO_VAL": 0, "NEGATIVE_VAL": -123}

    save_env_file(mock_env_file, values)

    expected_content = (
        "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
        "STRING_VAL=text\nINT_VAL=42\nZERO_VAL=0\nNEGATIVE_VAL=-123\n"
    )
    assert mock_env_file.write_text.call_args == mock.call(expected_content)


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_preserves_order(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = True
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    mock_read_env_file.return_value = {"B_KEY": "b_value", "A_KEY": "a_value"}
    new_values = {"D_KEY": "d_value", "C_KEY": "c_value"}

    save_env_file(mock_env_file, new_values)

    expected_content = (
        "# Docker Compose Environment Variables\n# Edit these values as needed\n\n"
        "B_KEY=b_value\nA_KEY=a_value\nD_KEY=d_value\nC_KEY=c_value\n"
    )
    assert mock_env_file.write_text.call_args == mock.call(expected_content)


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_path_methods_called_correctly(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = True
    mock_env_file.as_posix.return_value = "/test/path/.env"
    mock_read_env_file.return_value = {}
    values = {"KEY": "value"}

    save_env_file(mock_env_file, values)

    assert mock_env_file.exists.call_count == 1
    assert mock_env_file.as_posix.call_count == 1
    assert mock_env_file.write_text.call_count == 1


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_echo_messages(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.as_posix.return_value = "/test/path/.env"
    values = {"KEY": "value"}

    mock_env_file.exists.return_value = False
    save_env_file(mock_env_file, values)
    assert mock_echo.info.call_args == mock.call("Generated /test/path/.env.")

    mock_echo.reset_mock()
    mock_env_file.exists.return_value = True
    mock_read_env_file.return_value = {}
    save_env_file(mock_env_file, values)
    assert mock_echo.info.call_args == mock.call("Updated /test/path/.env.")


@mock.patch("deepfellow.common.config.echo")
@mock.patch("deepfellow.common.config.read_env_file")
def test_save_env_file_header_always_included(mock_read_env_file: mock.Mock, mock_echo: mock.Mock) -> None:
    mock_env_file = mock.Mock(spec=Path)
    mock_env_file.exists.return_value = False
    mock_env_file.as_posix.return_value = "/fake/path/.env"
    values = {"KEY": "value"}

    save_env_file(mock_env_file, values)

    written_content = mock_env_file.write_text.call_args[0][0]
    assert written_content.startswith("# Docker Compose Environment Variables\n# Edit these values as needed\n\n")
    assert "KEY=value\n" in written_content


@pytest.mark.parametrize(
    ("name", "existing"),
    [
        ("API_KEY", "existing-uuid-123"),
        ("SECRET_KEY", "another-existing-value"),
        ("JWT_SECRET", "old-uuid-value"),
    ],
)
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_keep_existing_confirmed(mock_echo: mock.Mock, name: str, existing: str) -> None:
    mock_echo.confirm.return_value = True

    result = configure_uuid_key(name, existing)

    assert result == existing
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call(
        f"There is an existing {name} in the env file. Do you want to keep it?", default=True
    )
    assert mock_echo.info.call_count == 0


@pytest.mark.parametrize(
    ("name", "existing"),
    [
        ("API_KEY", "existing-uuid-123"),
        ("SECRET_KEY", "another-existing-value"),
        ("JWT_SECRET", "old-uuid-value"),
    ],
)
@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_replace_existing_declined(
    mock_echo: mock.Mock, mock_uuid4: mock.Mock, name: str, existing: str
) -> None:
    mock_echo.confirm.return_value = False  # Don't keep existing
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="new-uuid-456")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid

    result = configure_uuid_key(name, existing)

    assert result == "new-uuid-456"
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call(
        f"There is an existing {name} in the env file. Do you want to keep it?", default=True
    )


@pytest.mark.parametrize(
    "name",
    [
        "API_KEY",
        "SECRET_KEY",
        "JWT_SECRET",
    ],
)
@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_no_existing(mock_echo: mock.Mock, mock_uuid4: mock.Mock, name: str) -> None:
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="generated-uuid-789")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid

    result = configure_uuid_key(name, None)

    assert result == "generated-uuid-789"


@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_replace_existing(mock_echo: mock.Mock, mock_uuid4: mock.Mock) -> None:
    mock_echo.confirm.return_value = False  # Don't keep existing
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="hidden-uuid-def")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid
    existing = "old-value"
    name = "SECRET_TOKEN"

    result = configure_uuid_key(name, existing)

    assert result == "hidden-uuid-def"
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args_list[0] == mock.call(
        "There is an existing SECRET_TOKEN in the env file. Do you want to keep it?", default=True
    )
    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_uuid4_called_when_generating_new(mock_echo: mock.Mock, mock_uuid4: mock.Mock) -> None:
    mock_echo.confirm.return_value = True
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="test-uuid")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid

    result = configure_uuid_key("TEST_KEY", None)

    assert mock_uuid4.call_count == 1
    assert mock_uuid4.call_args == mock.call()
    assert result == "test-uuid"


@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_uuid4_not_called_when_keeping_existing(mock_echo: mock.Mock) -> None:
    mock_echo.confirm.return_value = True
    existing = "keep-this-value"

    with mock.patch("deepfellow.common.config.uuid4") as mock_uuid4:
        result = configure_uuid_key("KEEP_KEY", existing)

    assert result == existing
    assert mock_uuid4.call_count == 0


@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_empty_string_existing_treated_as_string(
    mock_echo: mock.Mock, mock_uuid4: mock.Mock
) -> None:
    mock_echo.confirm.return_value = True
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="new-for-empty")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid

    result = configure_uuid_key("EMPTY_KEY", "")

    assert result == ""
    # Empty string is still considered existing, so should ask to keep it
    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args_list[0] == mock.call(
        "There is an existing EMPTY_KEY in the env file. Do you want to keep it?", default=True
    )


@mock.patch("deepfellow.common.config.uuid4")
@mock.patch("deepfellow.common.config.echo")
def test_configure_uuid_key_multiple_scenarios_in_sequence(mock_echo: mock.Mock, mock_uuid4: mock.Mock) -> None:
    mock_new_uuid = mock.Mock()
    mock_new_uuid.__str__ = mock.Mock(return_value="sequential-uuid")  # type: ignore[method-assign]
    mock_uuid4.return_value = mock_new_uuid

    # Scenario 1: Keep existing
    mock_echo.confirm.return_value = True
    result1 = configure_uuid_key("KEY1", "existing1")
    assert result1 == "existing1"

    # Reset mocks for next scenario
    mock_echo.reset_mock()
    mock_uuid4.reset_mock()
    mock_uuid4.return_value = mock_new_uuid

    # Scenario 2: Generate new
    mock_echo.confirm.return_value = False
    result2 = configure_uuid_key("KEY2", "existing2")
    assert result2 == "sequential-uuid"
    assert mock_echo.info.call_count == 0
