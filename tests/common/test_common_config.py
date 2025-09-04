import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import call, patch, Mock

import pytest
import typer

from deepfellow.common.config import get_config_path, load_config, store_config


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
def test_load_config_success(mock_get_config_path, context, temp_config_file):
    mock_get_config_path.return_value = temp_config_file

    result = load_config(context)

    expected = {"database": {"host": "localhost", "port": 5432}, "api": {"debug": True}}
    assert result == expected


@patch("deepfellow.common.config.get_config_path")
def test_load_config_empty_file(mock_get_config_path, context, tmp_path):
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("{}", encoding="utf-8")
    mock_get_config_path.return_value = empty_file

    result = load_config(context)

    assert result == {}


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_file_not_found(mock_get_config_path, mock_echo, tmp_path):
    nonexistent_file = tmp_path / "nonexistent.json"
    mock_get_config_path.return_value = nonexistent_file

    with pytest.raises(FileNotFoundError):
        load_config(raise_on_error=True)


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


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_json_decode_error(mock_get_config_path, mock_echo, context, temp_invalid_json_file):
    mock_get_config_path.return_value = temp_invalid_json_file

    with pytest.raises(typer.Exit) as exc_info:
        load_config(context)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Error parsing config file" in call_args[0]


@patch("deepfellow.common.config.echo")
@patch("deepfellow.common.config.get_config_path")
def test_load_config_unicode_decode_error(mock_get_config_path, mock_echo, context, temp_invalid_encoding_file):
    mock_get_config_path.return_value = temp_invalid_encoding_file

    with pytest.raises(typer.Exit) as exc_info:
        load_config(context)

    assert exc_info.value.exit_code == 1
    assert mock_echo.error.call_count == 1
    call_args = mock_echo.error.call_args[0]
    assert "Error reading config file (encoding issue)" in call_args[0]


@patch("deepfellow.common.config.get_config_path")
def test_load_config_complex_json(mock_get_config_path, context, tmp_path):
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

    result = load_config(context)

    assert result == complex_config
    assert result["database"]["connections"]["primary"]["host"] == "db1"
    assert "auth" in result["features"]["enabled"]


@patch("deepfellow.common.config.get_config_path")
def test_load_config_with_unicode_content(mock_get_config_path, context, tmp_path):
    unicode_config = {"app_name": "My App™", "description": "ćśńół", "emoji": "🚀"}
    config_file = tmp_path / "unicode.json"
    config_file.write_text(json.dumps(unicode_config, ensure_ascii=False), encoding="utf-8")
    mock_get_config_path.return_value = config_file

    result = load_config(context)

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
