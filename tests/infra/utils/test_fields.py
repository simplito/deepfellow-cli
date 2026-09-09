# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.infra.utils.fields import (
    build_spec_from_fields,
    format_field,
    normalize_field_description,
    parse_set_args,
    parse_spec_json,
    resolve_oneof_choices,
)


def test_normalize_field_description_collapses_embedded_newline() -> None:
    result = normalize_field_description("Custom enviromental variables.\nRequired variables: BRAVE_API_KEY")

    assert result == "Custom enviromental variables. Required variables: BRAVE_API_KEY"


def test_normalize_field_description_handles_non_string_input() -> None:
    assert normalize_field_description(None) == "None"


def test_format_field_renders_multiline_description_on_one_line() -> None:
    field = {
        "name": "envs",
        "description": "Custom enviromental variables.\nRequired variables: BRAVE_API_KEY",
        "default": '{"BRAVE_API_KEY": ""}',
    }

    result = format_field(field)

    assert (
        result
        == '- envs: Custom enviromental variables. Required variables: BRAVE_API_KEY (default: {"BRAVE_API_KEY": ""})'
    )
    assert "\n" not in result


def test_parse_spec_returns_empty_dict_when_none() -> None:
    result: dict[str, Any] = parse_spec_json(None)

    assert result == {}


def test_parse_set_args_parses_key_value_pairs() -> None:
    result: dict[str, str] = parse_set_args(["key=value", " spaced =trimmed"])

    assert result == {"key": "value", "spaced": "trimmed"}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_parse_set_args_raises_on_missing_equals_sign(mock_echo: Mock) -> None:
    with pytest.raises(typer.Exit):
        parse_set_args(["invalid-item"])

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Invalid --set value 'invalid-item'. Expected format: key=value")


def test_resolve_oneof_choices_normalizes_mixed_values() -> None:
    values: list[Any] = [{"value": "gpu"}, {"label": "no-value-key"}, "plain", 3]

    result: list[str] = resolve_oneof_choices(values)

    assert result == ["gpu", "{'label': 'no-value-key'}", "plain", "3"]


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_raises_when_field_missing_name(mock_echo: Mock) -> None:
    fields_spec: list[dict[str, Any]] = [{"type": "text", "required": False}]

    with pytest.raises(typer.Exit):
        build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Malformed spec: field missing 'name'. Please report this as a server bug."
    )


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_raises_when_field_missing_type(mock_echo: Mock) -> None:
    fields_spec: list[dict[str, Any]] = [{"name": "url", "required": False}]

    with pytest.raises(typer.Exit):
        build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call(
        "Malformed spec: field 'url' missing 'type'. Please report as a server bug."
    )


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_prefers_set_value_over_prompt(mock_echo: Mock) -> None:
    fields_spec: list[dict[str, Any]] = [
        {"name": "hardware", "type": "oneof", "required": True, "default": "GPU", "values": ["GPU", "CPU"]}
    ]

    result = build_spec_from_fields(fields_spec, {"hardware": "CPU"}, None, prompt_all=False)

    assert result == {"hardware": "CPU"}
    assert mock_echo.choice.call_count == 0


@mock.patch("deepfellow.infra.utils.fields.is_interactive", return_value=False)
@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_raises_when_required_field_missing_in_non_interactive_mode(
    mock_echo: Mock, mock_is_interactive: Mock
) -> None:
    fields_spec: list[dict[str, Any]] = [{"name": "token", "type": "text", "required": True, "default": None}]

    with pytest.raises(typer.Exit):
        build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert mock_echo.error.call_count == 1
    assert mock_echo.error.call_args == mock.call("Field 'token' is required. Use --set token=<value>")


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_prompts_oneof_choice_when_required(mock_echo: Mock) -> None:
    mock_echo.choice.return_value = "CPU"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "hardware",
            "type": "oneof",
            "required": True,
            "description": "Choose hardware",
            "default": "GPU",
            "values": [{"value": "GPU"}, {"value": "CPU"}],
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert result == {"hardware": "CPU"}
    assert mock_echo.choice.call_count == 1
    assert mock_echo.choice.call_args == mock.call("Choose hardware", choices=["GPU", "CPU"], default="GPU")


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_oneof_falls_back_to_first_choice_when_default_not_in_values(mock_echo: Mock) -> None:
    mock_echo.choice.return_value = "GPU"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "hardware",
            "type": "oneof",
            "required": True,
            "description": "Choose hardware",
            "default": "TPU",
            "values": [{"value": "GPU"}, {"value": "CPU"}],
        }
    ]

    build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert mock_echo.choice.call_args == mock.call("Choose hardware", choices=["GPU", "CPU"], default="GPU")


@mock.patch("deepfellow.infra.utils.fields.list_image_tags")
@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_prompts_docker_tag_choice_from_registry(
    mock_echo: Mock, mock_list_image_tags: Mock
) -> None:
    mock_list_image_tags.return_value = ["1.2.0", "1.1.0", "latest"]
    mock_echo.choice.return_value = "1.2.0"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "image_version",
            "type": "docker-tags",
            "required": False,
            "description": "Docker image version",
            "default": None,
            "docker_image": "hub.example.com/org/image",
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {"image_version": "1.2.0"}
    assert mock_list_image_tags.call_args == mock.call("hub.example.com/org/image")
    assert mock_echo.choice.call_count == 1
    assert mock_echo.choice.call_args == mock.call(
        "Docker image version", choices=["1.2.0", "1.1.0", "latest"], default="1.2.0"
    )


@mock.patch("deepfellow.infra.utils.fields.list_image_tags")
@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_docker_tag_falls_back_to_first_when_default_not_in_tags(
    mock_echo: Mock, mock_list_image_tags: Mock
) -> None:
    mock_list_image_tags.return_value = ["1.2.0", "1.1.0"]
    mock_echo.choice.return_value = "1.2.0"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "image_version",
            "type": "docker-tags",
            "required": False,
            "description": "Docker image version",
            "default": "unknown-tag",
            "docker_image": "hub.example.com/org/image",
        }
    ]

    build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert mock_echo.choice.call_args == mock.call("Docker image version", choices=["1.2.0", "1.1.0"], default="1.2.0")


@mock.patch("deepfellow.infra.utils.fields.list_image_tags")
@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_docker_tag_falls_back_to_text_prompt_when_registry_has_no_tags(
    mock_echo: Mock, mock_list_image_tags: Mock
) -> None:
    mock_list_image_tags.return_value = []
    mock_echo.prompt.return_value = "latest"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "image_version",
            "type": "docker-tags",
            "required": False,
            "description": "Docker image version",
            "default": None,
            "docker_image": "hub.example.com/org/image",
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {"image_version": "latest"}
    assert mock_echo.choice.call_count == 0
    assert mock_echo.prompt.call_count == 1


@mock.patch("deepfellow.infra.utils.fields.list_image_tags")
@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_skips_registry_lookup_when_docker_tag_field_not_prompted(
    mock_echo: Mock, mock_list_image_tags: Mock
) -> None:
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "image_version",
            "type": "docker-tags",
            "required": False,
            "description": "Docker image version",
            "default": "latest",
            "docker_image": "hub.example.com/org/image",
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert result == {}
    assert mock_list_image_tags.call_count == 0


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_prompts_required_password_field(mock_echo: Mock) -> None:
    mock_echo.prompt_until_valid.return_value = "secret-value"
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_key", "type": "password", "required": True, "description": "API Key", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert result == {"api_key": "secret-value"}
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_echo.prompt_until_valid.call_args.args[0] == "API Key"
    assert mock_echo.prompt_until_valid.call_args.kwargs["password"] is True
    assert mock_echo.prompt_until_valid.call_args.kwargs["error_message"] == (
        "'api_key' is required and cannot be empty. You can use --set api_key=value instead."
    )


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_exits_when_optional_password_left_empty_and_not_confirmed(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = ""
    mock_echo.confirm.return_value = False
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_key", "type": "password", "required": False, "description": "API Key", "default": None}
    ]

    with pytest.raises(typer.Exit):
        build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert mock_echo.confirm.call_count == 1
    assert mock_echo.confirm.call_args == mock.call("'api_key' is empty. Do you want to continue?")


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_skips_optional_password_when_left_empty_and_confirmed(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = ""
    mock_echo.confirm.return_value = True
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_key", "type": "password", "required": False, "description": "API Key", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_adds_optional_password_when_value_given(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = "typed-secret"
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_key", "type": "password", "required": False, "description": "API Key", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {"api_key": "typed-secret"}
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_adds_text_field_value_when_provided(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = "typed-url"
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_url", "type": "text", "required": False, "description": "API URL", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {"api_url": "typed-url"}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_skips_optional_text_field_when_left_empty(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = ""
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_url", "type": "text", "required": False, "description": "API URL", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_adds_required_text_field_even_when_value_is_empty(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = ""
    fields_spec: list[dict[str, Any]] = [
        {"name": "name", "type": "text", "required": True, "description": "Name", "default": None}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert result == {"name": ""}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_adds_text_field_with_default_when_value_given(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = "https://custom.example.com"
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "api_url",
            "type": "text",
            "required": False,
            "description": "API URL",
            "default": "https://default.example.com",
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {"api_url": "https://custom.example.com"}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_skips_text_field_with_default_when_prompt_returns_empty(mock_echo: Mock) -> None:
    mock_echo.prompt.return_value = ""
    fields_spec: list[dict[str, Any]] = [
        {
            "name": "api_url",
            "type": "text",
            "required": False,
            "description": "API URL",
            "default": "https://default.example.com",
        }
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=True)

    assert result == {}


@mock.patch("deepfellow.infra.utils.fields.echo")
def test_build_spec_from_fields_skips_optional_field_without_prompt_all(mock_echo: Mock) -> None:
    fields_spec: list[dict[str, Any]] = [
        {"name": "api_url", "type": "text", "required": False, "description": "API URL", "default": "https://x"}
    ]

    result = build_spec_from_fields(fields_spec, {}, None, prompt_all=False)

    assert result == {}
    assert mock_echo.prompt.call_count == 0
