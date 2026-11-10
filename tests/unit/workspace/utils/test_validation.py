# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from pathlib import Path

import pytest
import typer

from deepfellow.workspace.utils.validation import (
    check_workspace_directory,
    validate_flag,
    validate_mcp_auth_token,
    validate_port_text,
)


def test_check_workspace_directory_with_compose_file_passes(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text("services: {}")

    check_workspace_directory(tmp_path)


def test_check_workspace_directory_without_compose_file_exits(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        check_workspace_directory(tmp_path)


def test_check_workspace_directory_missing_directory_exits(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        check_workspace_directory(tmp_path / "nope")


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("x" * 16, "x" * 16), ("  " + "x" * 16 + "  ", "x" * 16)],
    ids=["none", "long_enough", "stripped"],
)
def test_installvalidate_mcp_auth_token_returns_value(value: str | None, expected: str | None) -> None:
    assert validate_mcp_auth_token(value) == expected


@pytest.mark.parametrize("value", ["short", " " * 5 + "x" * 15], ids=["short", "short_after_stripping"])
def test_installvalidate_mcp_auth_token_rejects_short_token(value: str) -> None:
    with pytest.raises(typer.BadParameter):
        validate_mcp_auth_token(value)


def test_validate_port_text_returns_port_as_text():
    result = validate_port_text("3001")

    assert result == "3001"


@pytest.mark.parametrize("value", ["0", "70000", "abc"])
def test_validate_port_text_rejects_invalid_port(value: str):
    with pytest.raises(typer.BadParameter):
        validate_port_text(value)


@pytest.mark.parametrize(("value", "expected"), [("true", "true"), ("FALSE", "false"), ("True", "true")])
def test_validate_flag_returns_lower_case(value: str, expected: str):
    result = validate_flag(value)

    assert result == expected


@pytest.mark.parametrize("value", ["yes", "1", "on"])
def test_validate_flag_rejects_other_values(value: str):
    with pytest.raises(typer.BadParameter):
        validate_flag(value)
