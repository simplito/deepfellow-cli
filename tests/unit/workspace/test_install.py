# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.workspace.install import _not_empty, install, install_workspace

_REQUIRED_KEYS = (
    "DF_SERVER_URL",
    "DF_SERVER_API_KEY",
    "DF_SERVER_ORGANIZATION_ID",
    "DF_SERVER_PROJECT_ID",
    "SMALL_MODEL",
)
_OPTIONAL_FLAGS = (
    "admin_name",
    "admin_email",
    "admin_password",
    "smtp_host",
    "smtp_port",
    "smtp_secure",
    "smtp_username",
    "smtp_password",
    "email_from_address",
    "email_from_name",
    "mongodb_url",
    "mongodb_database_name",
    "redis_url",
    "trusted_proxy",
    "trusted_origins",
    "mcp_auth_token",
)


@pytest.fixture(autouse=True)
def mock_prompt_optional() -> Iterator[Mock]:
    with mock.patch("deepfellow.workspace.install.prompt_optional_settings") as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_address_interactive() -> Iterator[Mock]:
    """Keep the address questions quiet; tests that need them set `return_value = True`."""
    with mock.patch("deepfellow.workspace.utils.public_url.is_interactive", return_value=False) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_configure_webhook() -> Iterator[Mock]:
    with mock.patch("deepfellow.workspace.install.configure_webhook") as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_resolve_server_ids() -> Iterator[Mock]:
    with mock.patch("deepfellow.workspace.install.resolve_server_ids", return_value=None) as mocked:
        yield mocked


@pytest.fixture(autouse=True)
def mock_list_server_models() -> Iterator[Mock]:
    with mock.patch("deepfellow.workspace.install.list_server_models", return_value=None) as mocked:
        yield mocked


def _call(directory: Path, **overrides: Any) -> None:
    kwargs: dict[str, Any] = {
        "directory": directory,
        "image": "img:1",
        "local_image": None,
        "port": 3000,
        "bind_address": "",
        "docker_network": "net",
        "public_url": None,
        "df_server_url": "https://df.example.com/v1",
        "df_server_api_key": "key",
        "df_server_organization_id": "org",
        "df_server_project_id": "proj",
        "small_model": "small",
        "force_install": False,
        "local_mongodb": False,
        "local_redis": False,
        "no_smtp": False,
        "no_server_webhook": False,
    } | dict.fromkeys(_OPTIONAL_FLAGS)
    install(**(kwargs | overrides))


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
def test_install_passes_values_to_util_and_reports_stored_url(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    _call(tmp_path)

    assert mock_util.call_args.kwargs == {
        "directory": tmp_path,
        "image": "img:1",
        "port": 3000,
        "bind_address": "",
        "docker_network": "net",
        "existing": {},
        "passed": {
            "DF_SERVER_URL": "https://df.example.com/v1",
            "DF_SERVER_API_KEY": "key",
            "DF_SERVER_ORGANIZATION_ID": "org",
            "DF_SERVER_PROJECT_ID": "proj",
            "SMALL_MODEL": "small",
            "PUBLIC_URL": None,
            "BOOTSTRAP_ADMIN_NAME": None,
            "BOOTSTRAP_ADMIN_EMAIL": None,
            "BOOTSTRAP_ADMIN_PASSWORD": None,
            "SMTP_HOST": None,
            "SMTP_PORT": None,
            "SMTP_SECURE": None,
            "SMTP_USERNAME": None,
            "SMTP_PASSWORD": None,
            "EMAIL_FROM_ADDRESS": None,
            "EMAIL_FROM_NAME": None,
            "MONGO_DB_URL": None,
            "MONGO_DB_NAME": None,
            "REDIS_URL": None,
            "TRUSTED_PROXY_ENABLED": None,
            "TRUSTED_ORIGINS": None,
            "MCP_AUTH_TOKEN": None,
        },
        "force_install": False,
        "overwrite": True,
        "reset": (),
        "local_image": False,
        "retry_hint": "run 'workspace install --force-install' again (secrets are kept)",
    }
    assert mock_echo.success.call_args == mock.call("DeepFellow Workspace installed. Open it at http://localhost:3000.")


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
def test_install_non_interactive_missing_value_names_it_and_exits(
    mock_echo: Mock, mock_assert_docker: Mock, mock_interactive: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", df_server_api_key=None)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert "DF_SERVER_API_KEY" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_existing_env_supplies_missing_value(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_confirm: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DF_SERVER_API_KEY=old\n")

    _call(tmp_path, df_server_api_key=None)

    assert mock_echo.error.call_count == 0
    assert mock_util.call_args.kwargs["existing"] == {"DF_SERVER_API_KEY": "old"}


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_prompts_for_missing_value(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_confirm: Mock,
    tmp_path: Path,
) -> None:
    mock_echo.prompt_until_valid.return_value = "typed"

    _call(tmp_path, df_server_organization_id=None)

    assert mock_util.call_args.kwargs["passed"]["DF_SERVER_ORGANIZATION_ID"] == "typed"
    assert mock_echo.prompt_until_valid.call_count == 1
    assert mock_echo.prompt_until_valid.call_args.kwargs == {"default": None, "password": False}


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_interactive_masks_api_key_prompt_and_offers_existing_as_default(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DF_SERVER_PROJECT_ID=p\n")
    mock_echo.prompt_until_valid.return_value = "typed"

    _call(tmp_path, df_server_api_key=None, df_server_project_id=None)

    assert mock_echo.prompt_until_valid.call_count == 2
    assert mock_echo.prompt_until_valid.call_args_list[0].kwargs == {"default": None, "password": True}
    assert mock_echo.prompt_until_valid.call_args_list[1].kwargs == {"default": "p", "password": False}
    assert mock_util.call_args.kwargs["passed"]["DF_SERVER_PROJECT_ID"] == "typed"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_url_prompt_is_validated(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_confirm: Mock,
    tmp_path: Path,
) -> None:
    mock_echo.prompt_until_valid.return_value = "https://df.example.com/v1"

    _call(tmp_path, df_server_url=None)

    assert mock_echo.prompt_until_valid.call_args.args[1].__name__ == "validate_url"


def test_install_not_empty_rejects_blank() -> None:
    with pytest.raises(typer.BadParameter):
        _not_empty("   ")
    assert _not_empty(" x ") == "x"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", side_effect=InstallError("boom"))
def test_install_util_error_is_reported_and_exits(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        _call(tmp_path)

    assert mock_echo.error.call_args == mock.call("boom")


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_unreadable_existing_env_is_reported_and_exits(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_bytes(b"\xff\xfe\x00bad")

    with pytest.raises(typer.Exit):
        _call(tmp_path)

    assert mock_echo.error.call_count == 1
    assert mock_util.call_count == 0


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_existing_directory_asks_overwrite_before_value_prompts(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    manager = Mock()
    manager.attach_mock(mock_confirm, "confirm")
    manager.attach_mock(mock_echo.prompt_until_valid, "prompt")
    mock_echo.prompt_until_valid.return_value = "typed"

    _call(tmp_path, df_server_organization_id=None)

    assert [call[0] for call in manager.mock_calls] == ["confirm", "prompt"]


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util")
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=False)
def test_install_declined_overwrite_exits_without_prompting(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    with pytest.raises(typer.Exit):
        _call(tmp_path, df_server_organization_id=None)

    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_util.call_count == 0


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_optional_flags_are_passed_as_env_values(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_prompt_optional: Mock, tmp_path: Path
) -> None:
    _call(
        tmp_path / "ws",
        smtp_port=465,
        smtp_secure=True,
        trusted_proxy=False,
        mongodb_url="mongodb://db:27017/?replicaSet=rs0",
        redis_url="redis://cache:6379",
        mcp_auth_token="x" * 16,
    )

    passed = mock_util.call_args.kwargs["passed"]
    assert passed["SMTP_PORT"] == "465"
    assert passed["SMTP_SECURE"] == "true"
    assert passed["TRUSTED_PROXY_ENABLED"] == "false"
    assert passed["MONGO_DB_URL"] == "mongodb://db:27017/?replicaSet=rs0"
    assert passed["REDIS_URL"] == "redis://cache:6379"
    assert mock_prompt_optional.call_args == mock.call(passed, {})


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_non_interactive_reports_values_kept_from_existing_env_without_showing_the_api_key(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DF_SERVER_URL=http://127.0.0.1:8000\nDF_SERVER_API_KEY=secret\n")

    _call(tmp_path, df_server_url=None, df_server_api_key=None)

    messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "DeepFellow Server URL: http://127.0.0.1:8000 (kept from the existing installation)" in messages
    assert "DeepFellow Server project API key: (hidden) (kept from the existing installation)" in messages
    assert not any("secret" in message for message in messages)
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_interactive_existing_values_are_prompted_with_themselves_as_default(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DF_SERVER_URL=http://127.0.0.1:8000\nDF_SERVER_API_KEY=secret\n")
    mock_echo.prompt_until_valid.side_effect = lambda label, validation, **kwargs: kwargs["default"] or "typed"

    _call(tmp_path, df_server_url=None, df_server_api_key=None, small_model=None)

    calls = mock_echo.prompt_until_valid.call_args_list
    assert calls[0].kwargs == {"default": "http://127.0.0.1:8000", "password": False}
    assert calls[1].kwargs == {"default": "secret", "password": True}
    assert calls[2].kwargs == {"default": "gemma4:e4b", "password": False}
    assert mock_util.call_args.kwargs["passed"]["DF_SERVER_URL"] == "http://127.0.0.1:8000"
    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "gemma4:e4b"


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_small_model_question_is_explained_and_defaults_to_gemma(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_interactive: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws", small_model=None)

    explanation = mock_echo.info.call_args.args[0]
    assert "background tasks" in explanation
    assert "session titles" in explanation
    assert mock_echo.prompt_until_valid.call_args.args[0] == "Small model name served by DeepFellow Server"
    assert mock_echo.prompt_until_valid.call_args.kwargs == {"default": "gemma4:e4b", "password": False}


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_many_server_models_without_default_prompt_without_default_and_validate(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    models = [f"m{i}" for i in range(11)]
    mock_list_server_models.return_value = models

    _call(tmp_path / "ws", small_model=None)

    kwargs = mock_echo.prompt_until_valid.call_args.kwargs
    validation = mock_echo.prompt_until_valid.call_args.args[1]
    assert mock_echo.choice.call_count == 0
    assert kwargs["default"] is None
    assert validation("m3") == "m3"
    with pytest.raises(typer.BadParameter):
        validation("typo")


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_interactive_existing_small_model_is_the_default_instead_of_gemma(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("SMALL_MODEL=other\n")

    _call(tmp_path, small_model=None)

    assert mock_echo.prompt_until_valid.call_args.kwargs["default"] == "other"


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_small_model_defaults_to_gemma(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_interactive: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws", small_model=None)

    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "gemma4:e4b"
    assert mock_echo.info.call_args == mock.call("Small model name served by DeepFellow Server: gemma4:e4b (default)")


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
def test_install_takes_organization_and_project_ids_from_server(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    mock_resolve_server_ids.return_value = ("org-from-server", "proj-from-server")

    _call(tmp_path, df_server_organization_id=None, df_server_project_id=None)

    assert mock_resolve_server_ids.call_count == 1
    assert mock_resolve_server_ids.call_args == mock.call("https://df.example.com/v1", "key")
    passed = mock_util.call_args.kwargs["passed"]
    assert passed["DF_SERVER_ORGANIZATION_ID"] == "org-from-server"
    assert passed["DF_SERVER_PROJECT_ID"] == "proj-from-server"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
def test_install_keeps_explicit_organization_id_when_server_reports_ids(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    mock_resolve_server_ids.return_value = ("org-from-server", "proj-from-server")

    _call(tmp_path, df_server_organization_id="explicit-org", df_server_project_id=None)

    passed = mock_util.call_args.kwargs["passed"]
    assert passed["DF_SERVER_ORGANIZATION_ID"] == "explicit-org"
    assert passed["DF_SERVER_PROJECT_ID"] == "proj-from-server"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_non_interactive_without_ids_from_server_names_missing_value(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, df_server_organization_id=None, df_server_project_id=None)

    assert mock_util.call_args.kwargs["passed"]["DF_SERVER_ORGANIZATION_ID"] is None
    assert mock_util.call_args.kwargs["passed"]["DF_SERVER_PROJECT_ID"] is None


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_does_not_ask_server_for_ids_without_api_key(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, df_server_api_key=None, df_server_organization_id=None, df_server_project_id=None)

    assert mock_resolve_server_ids.call_count == 0


@mock.patch("deepfellow.workspace.install.server_lookup_failed", return_value=True)
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_does_not_warn_again_when_server_lookup_already_failed(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_failed: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, df_server_organization_id=None, df_server_project_id=None)

    assert mock_echo.warning.call_count == 0
    assert any("--df-server-organization-id" in call.args[0] for call in mock_echo.info.call_args_list)


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_warns_once_when_server_does_not_report_ids(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, df_server_organization_id=None, df_server_project_id=None)

    assert mock_resolve_server_ids.call_count == 1
    assert mock_echo.warning.call_count == 1
    assert "--df-server-organization-id" in mock_echo.warning.call_args.args[0]


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_does_not_ask_server_when_both_ids_are_given(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path)

    assert mock_resolve_server_ids.call_count == 0
    assert mock_echo.warning.call_count == 0


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_single_server_model_is_chosen_without_asking(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = ["only-one"]

    _call(tmp_path / "ws", small_model=None)

    assert mock_list_server_models.call_args == mock.call("https://df.example.com/v1", "key")
    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "only-one"
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_echo.choice.call_count == 0
    assert mock_echo.info.call_args == mock.call(
        "Only one model is available on DeepFellow Server, using it as the small model: only-one"
    )


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_single_server_model_is_chosen(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = ["only-one"]

    _call(tmp_path / "ws", small_model=None)

    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "only-one"


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_few_server_models_without_default_are_offered_as_choice(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = ["a", "b"]
    mock_echo.choice.return_value = "b"

    _call(tmp_path / "ws", small_model=None)

    assert mock_echo.choice.call_args == mock.call("Small model name served by DeepFellow Server", ["a", "b"])
    assert mock_echo.prompt_until_valid.call_count == 0
    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "b"


@pytest.mark.parametrize("models", [["a", "gemma4:e4b"]])
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_server_models_with_default_still_prompt_with_default(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    models: list[str],
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = models

    _call(tmp_path / "ws", small_model=None)

    assert mock_echo.choice.call_count == 0
    assert mock_echo.prompt_until_valid.call_args.kwargs == {"default": "gemma4:e4b", "password": False}


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_server_models_without_default_fails_asking_for_small_model(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = ["a", "b"]

    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", small_model=None)

    assert mock_util.call_count == 0
    assert "--small-model" in mock_echo.error.call_args.args[0]
    assert "a, b" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
def test_install_existing_small_model_and_explicit_flag_skip_server_models_lookup(
    mock_confirm: Mock,
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "SMALL_MODEL=other\nDF_SERVER_URL=https://df.example.com/v1\nDF_SERVER_API_KEY=key\n"
    )
    mock_list_server_models.return_value = ["only-one"]

    _call(tmp_path, small_model=None)
    _call(tmp_path, small_model="flag")

    assert mock_list_server_models.call_count == 0
    assert mock_echo.prompt_until_valid.call_args.kwargs["default"] == "other"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
def test_install_non_interactive_reinstall_with_new_api_key_replaces_kept_ids_using_kept_url(
    mock_util: Mock,
    mock_is_interactive: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_resolve_server_ids: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("DF_SERVER_URL=http://kept:8000/v1\nDF_SERVER_API_KEY=old\n")
    mock_resolve_server_ids.return_value = ("new-org", "new-proj")

    _call(
        tmp_path, df_server_url=None, df_server_api_key="new", df_server_organization_id=None, df_server_project_id=None
    )

    assert mock_resolve_server_ids.call_args == mock.call("http://kept:8000/v1", "new")
    passed = mock_util.call_args.kwargs["passed"]
    assert passed["DF_SERVER_ORGANIZATION_ID"] == "new-org"
    assert passed["DF_SERVER_PROJECT_ID"] == "new-proj"


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_cancelled_small_model_choice_exits(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = ["a", "b"]
    mock_echo.choice.return_value = None

    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", small_model=None)

    assert mock_util.call_count == 0


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_server_reporting_no_models_fails_asking_for_small_model(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    mock_list_server_models.return_value = []

    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", small_model=None)

    assert mock_echo.warning.call_args == mock.call("DeepFellow Server reports no models for this API key's project.")
    assert mock_util.call_count == 0
    assert "--small-model" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_reinstall_with_new_api_key_checks_kept_small_model(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_confirm: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "SMALL_MODEL=old\nDF_SERVER_URL=https://df.example.com/v1\nDF_SERVER_API_KEY=old-key\n"
    )
    mock_list_server_models.return_value = ["a", "b"]

    with pytest.raises(typer.Exit):
        _call(tmp_path, small_model=None)

    assert mock_list_server_models.call_args == mock.call("https://df.example.com/v1", "key")
    assert mock_util.call_count == 0
    assert "--small-model" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
def test_install_reset_flags_pass_keys_to_forget_to_util(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    _call(tmp_path, local_mongodb=True, local_redis=True, no_smtp=True)

    reset = mock_util.call_args.kwargs["reset"]
    assert {"MONGO_DB_URL", "MONGO_DB_NAME", "REDIS_URL", "SMTP_HOST", "SMTP_PORT", "EMAIL_FROM_NAME"} <= set(reset)


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_local_mongodb_with_external_url_exits(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", local_mongodb=True, mongodb_url="mongodb://x/?replicaSet=rs0")

    assert mock_util.call_count == 0
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_no_smtp_with_smtp_setting_exits(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    with pytest.raises(typer.Exit):
        _call(tmp_path / "ws", no_smtp=True, smtp_host="smtp.example.com")

    assert mock_util.call_count == 0
    assert mock_echo.error.call_count == 1


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch(
    "deepfellow.workspace.install.install_util",
    return_value={"PUBLIC_URL": "http://localhost:3000", "BOOTSTRAP_ADMIN_PASSWORD": "pw"},
)
def test_install_with_admin_password_says_it_stays_in_env(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    _call(tmp_path)

    assert "BOOTSTRAP_ADMIN_*" in mock_echo.info.call_args.args[0]


@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_without_server_credentials_uses_default_small_model_without_lookup(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path / "ws", df_server_url=None, df_server_api_key=None, small_model=None)

    assert mock_list_server_models.call_count == 0
    assert mock_util.call_args.kwargs["passed"]["SMALL_MODEL"] == "gemma4:e4b"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_reinstall_keeps_small_model_offered_by_new_api_key(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_interactive: Mock,
    mock_confirm: Mock,
    mock_list_server_models: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text(
        "SMALL_MODEL=a\nDF_SERVER_URL=https://df.example.com/v1\nDF_SERVER_API_KEY=old-key\n"
    )
    mock_list_server_models.return_value = ["a", "b"]

    _call(tmp_path, small_model=None)

    assert mock_list_server_models.call_count == 1
    assert "SMALL_MODEL" not in {k for k, v in mock_util.call_args.kwargs["passed"].items() if v}


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_http_lan_address_warns_and_installs(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws", public_url="http://192.168.1.10:3000")

    assert mock_echo.warning.call_count == 1
    assert "http://192.168.1.10:3000" in mock_echo.warning.call_args.args[0]
    assert mock_util.call_count == 1
    assert mock_util.call_args.kwargs["passed"]["TRUSTED_PROXY_ENABLED"] is None


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_default_address_does_not_warn(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws")

    assert mock_echo.warning.call_count == 0
    assert mock_util.call_args.kwargs["passed"]["PUBLIC_URL"] is None


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_https_address_enables_trusted_proxy(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws", public_url="https://ws.example.com", trusted_origins="https://a.example.com")

    passed = mock_util.call_args.kwargs["passed"]
    assert mock_echo.warning.call_count == 0
    assert passed["TRUSTED_PROXY_ENABLED"] == "true"
    assert passed["TRUSTED_ORIGINS"] == "https://a.example.com"


@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_https_address_keeps_explicit_no_trusted_proxy(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, tmp_path: Path
) -> None:
    _call(tmp_path / "ws", public_url="https://ws.example.com", trusted_proxy=False)

    assert mock_util.call_args.kwargs["passed"]["TRUSTED_PROXY_ENABLED"] == "false"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_reinstall_kept_http_lan_address_warns(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("PUBLIC_URL=http://10.0.0.5:3000\n")

    _call(tmp_path)

    assert mock_echo.warning.call_count == 1
    assert "http://10.0.0.5:3000" in mock_echo.warning.call_args.args[0]
    assert mock_util.call_count == 1


@mock.patch("deepfellow.workspace.utils.public_url.echo")
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_asks_for_address_and_extra_origins(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_address_echo: Mock,
    mock_address_interactive: Mock,
    tmp_path: Path,
) -> None:
    mock_address_interactive.return_value = True
    mock_address_echo.prompt_until_valid.side_effect = ["https://ws.example.com", "https://a.example.com"]

    _call(tmp_path / "ws")

    passed = mock_util.call_args.kwargs["passed"]
    assert mock_address_echo.prompt_until_valid.call_count == 2
    assert passed["PUBLIC_URL"] == "https://ws.example.com"
    assert passed["TRUSTED_PROXY_ENABLED"] == "true"
    assert passed["TRUSTED_ORIGINS"] == "https://a.example.com"


@mock.patch("deepfellow.workspace.utils.public_url.state")
@mock.patch("deepfellow.workspace.utils.public_url.echo")
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_yes_reinstall_over_https_keeps_settings_without_asking(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_address_echo: Mock,
    mock_state: Mock,
    mock_address_interactive: Mock,
    tmp_path: Path,
) -> None:
    mock_address_interactive.return_value = True
    mock_state.yes = True
    (tmp_path / ".env").write_text(
        "PUBLIC_URL=https://ws.example.com\nTRUSTED_PROXY_ENABLED=false\nTRUSTED_ORIGINS=https://a.example.com\n"
    )

    _call(tmp_path)

    passed = mock_util.call_args.kwargs["passed"]
    assert mock_address_echo.prompt_until_valid.call_count == 0
    assert mock_echo.warning.call_count == 0
    assert passed["PUBLIC_URL"] is None
    assert passed["TRUSTED_PROXY_ENABLED"] is None
    assert passed["TRUSTED_ORIGINS"] is None


@mock.patch("deepfellow.workspace.utils.public_url.echo")
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_reinstall_offers_previous_address_and_origins(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_address_echo: Mock,
    mock_address_interactive: Mock,
    tmp_path: Path,
) -> None:
    mock_address_interactive.return_value = True
    mock_address_echo.prompt_until_valid.side_effect = ["https://ws.example.com", "https://a.example.com"]
    (tmp_path / ".env").write_text("PUBLIC_URL=https://ws.example.com\nTRUSTED_ORIGINS=https://a.example.com\n")

    _call(tmp_path)

    calls = mock_address_echo.prompt_until_valid.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["default"] == "https://ws.example.com"
    assert calls[1].kwargs["default"] == "https://a.example.com"
    assert mock_util.call_args.kwargs["passed"]["TRUSTED_PROXY_ENABLED"] == "true"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util")
def test_install_invalid_kept_address_reports_error_and_exits(
    mock_util: Mock, mock_echo: Mock, mock_assert_docker: Mock, mock_confirm: Mock, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text("PUBLIC_URL=not-a-url\n")

    with pytest.raises(typer.Exit):
        _call(tmp_path)

    assert mock_util.call_count == 0
    assert "PUBLIC_URL" in mock_echo.error.call_args.args[0]


@mock.patch("deepfellow.workspace.utils.public_url.echo")
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_non_interactive_reinstall_over_https_keeps_proxy_trust_off(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_address_echo: Mock,
    tmp_path: Path,
) -> None:
    (tmp_path / ".env").write_text("PUBLIC_URL=https://ws.example.com\nTRUSTED_PROXY_ENABLED=false\n")

    _call(tmp_path)

    passed = mock_util.call_args.kwargs["passed"]
    assert mock_address_echo.prompt_until_valid.call_count == 0
    assert passed["PUBLIC_URL"] is None
    assert passed["TRUSTED_PROXY_ENABLED"] is None


@mock.patch("deepfellow.common.echo.Prompt.ask")
@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "u"})
def test_install_interactive_reinstall_blank_origins_answer_keeps_previous_list(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_ask: Mock,
    mock_address_interactive: Mock,
    tmp_path: Path,
) -> None:
    # TRUSTED_ORIGINS cannot be cleared by a blank answer: it maps to "not given", which keeps the previous list.
    mock_address_interactive.return_value = True
    mock_ask.side_effect = ["https://ws.example.com", " , "]
    (tmp_path / ".env").write_text("PUBLIC_URL=https://ws.example.com\nTRUSTED_ORIGINS=https://a.example.com\n")

    _call(tmp_path)

    assert mock_ask.call_count == 2
    assert mock_util.call_args.kwargs["passed"]["TRUSTED_ORIGINS"] is None


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "https://ws.example.com"})
def test_install_sets_up_webhook_for_the_chosen_address(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_configure_webhook: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, public_url="https://ws.example.com")

    assert mock_configure_webhook.call_count == 1
    assert mock_configure_webhook.call_args.args[2] == "https://ws.example.com"


@mock.patch("deepfellow.workspace.install.confirm_overwrite", return_value=True)
@mock.patch("deepfellow.workspace.install.assert_docker")
@mock.patch("deepfellow.workspace.install.echo")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "https://ws.example.com"})
def test_install_skips_webhook_setup_with_no_server_webhook(
    mock_util: Mock,
    mock_echo: Mock,
    mock_assert_docker: Mock,
    mock_confirm: Mock,
    mock_configure_webhook: Mock,
    tmp_path: Path,
) -> None:
    _call(tmp_path, public_url="https://ws.example.com", no_server_webhook=True)

    assert mock_configure_webhook.call_count == 0
    assert mock_util.call_count == 1


@mock.patch("deepfellow.workspace.install.prompt_optional_settings")
@mock.patch("deepfellow.workspace.install.configure_webhook")
@mock.patch("deepfellow.workspace.install.install_util", return_value={"PUBLIC_URL": "http://localhost:3000"})
@mock.patch("deepfellow.workspace.install.assert_docker")
def test_install_workspace_skips_optional_questions_and_forwards_cli_server_url(
    mock_assert_docker: Mock,
    mock_install_util: Mock,
    mock_configure_webhook: Mock,
    mock_prompt_optional: Mock,
    tmp_path: Path,
) -> None:
    passed: dict[str, str | None] = dict.fromkeys(_REQUIRED_KEYS, "value")
    passed["PUBLIC_URL"] = "https://ws.example.com"

    env = install_workspace(
        passed,
        directory=tmp_path / "workspace",
        ask_optional_settings=False,
        cli_server_url="http://localhost:8000",
    )

    assert env == {"PUBLIC_URL": "http://localhost:3000"}
    assert mock_prompt_optional.call_count == 0
    assert mock_configure_webhook.call_args == mock.call(passed, {}, "https://ws.example.com", "http://localhost:8000")
    assert mock_install_util.call_count == 1
