# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from deepfellow.common.validation import validate_mongo_url, validate_redis_url
from deepfellow.workspace.utils.configure import prompt_optional_settings


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=False)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_non_interactive_asks_nothing(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {})

    assert passed == {}
    assert mock_echo.confirm.call_count == 0
    assert mock_echo.prompt_until_valid.call_count == 0


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_reinstall_asks_nothing(mock_echo: Mock, mock_interactive: Mock) -> None:
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {"APP_SECRET": "x"})

    assert passed == {}
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.workspace.utils.configure.resolve_admin_creds")
@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_declining_everything_stores_nothing(
    mock_echo: Mock, mock_interactive: Mock, mock_admin: Mock
) -> None:
    mock_echo.confirm.side_effect = [True, True, False, False]
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {})

    assert passed == {}
    assert [call.args[0] for call in mock_echo.confirm.call_args_list] == [
        "Install a local MongoDB for DeepFellow Workspace?",
        "Install a local Redis for DeepFellow Workspace?",
        "Create an initial admin account?",
        "Configure sending e-mails (SMTP)?",
    ]
    assert mock_admin.call_count == 0
    assert mock_echo.confirm.call_args_list[0].kwargs == {"default": True, "ignore_yes": True}


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_external_services_ask_for_urls(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.confirm.side_effect = [False, False, False, False]
    mock_echo.prompt_until_valid.side_effect = ["mongodb://db/?replicaSet=rs0", "redis://cache"]
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {})

    assert passed == {"MONGO_DB_URL": "mongodb://db/?replicaSet=rs0", "REDIS_URL": "redis://cache"}
    assert mock_echo.prompt_until_valid.call_args_list[0].args[1] is validate_mongo_url
    assert mock_echo.prompt_until_valid.call_args_list[1].args[1] is validate_redis_url


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_service_url_from_flag_is_not_asked_about(
    mock_echo: Mock, mock_interactive: Mock
) -> None:
    mock_echo.confirm.side_effect = [False, False]
    passed: dict[str, str | None] = {"MONGO_DB_URL": "mongodb://db", "REDIS_URL": "redis://cache"}

    prompt_optional_settings(passed, {})

    assert [call.args[0] for call in mock_echo.confirm.call_args_list] == [
        "Create an initial admin account?",
        "Configure sending e-mails (SMTP)?",
    ]


@mock.patch("deepfellow.workspace.utils.configure.resolve_admin_creds", return_value=("Ann", "ann@example.com", "Pw1!"))
@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_admin_is_resolved_and_stored(
    mock_echo: Mock, mock_interactive: Mock, mock_admin: Mock
) -> None:
    mock_echo.confirm.side_effect = [True, True, True, False]
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {})

    assert mock_admin.call_args == mock.call(None, None, None)
    assert passed["BOOTSTRAP_ADMIN_NAME"] == "Ann"
    assert passed["BOOTSTRAP_ADMIN_EMAIL"] == "ann@example.com"
    assert passed["BOOTSTRAP_ADMIN_PASSWORD"] == "Pw1!"


@mock.patch("deepfellow.workspace.utils.configure.resolve_admin_creds", return_value=("Ann", "ann@example.com", "Pw1!"))
@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_partial_admin_flags_skip_confirm_and_ask_the_rest(
    mock_echo: Mock, mock_interactive: Mock, mock_admin: Mock
) -> None:
    mock_echo.confirm.side_effect = [True, True, False]
    passed: dict[str, str | None] = {"BOOTSTRAP_ADMIN_EMAIL": "ann@example.com"}

    prompt_optional_settings(passed, {})

    assert mock_admin.call_args == mock.call(None, "ann@example.com", None)
    assert "Create an initial admin account?" not in [call.args[0] for call in mock_echo.confirm.call_args_list]


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_smtp_asks_every_missing_value(mock_echo: Mock, mock_interactive: Mock) -> None:
    mock_echo.confirm.side_effect = [True, True, False, True, True]
    mock_echo.prompt_until_valid.side_effect = ["smtp.example.com", 465, "user", "secret", "no-reply@example.com"]
    mock_echo.prompt.return_value = "Workspace"
    passed: dict[str, str | None] = {}

    prompt_optional_settings(passed, {})

    assert passed == {
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "465",
        "SMTP_SECURE": "true",
        "SMTP_USERNAME": "user",
        "SMTP_PASSWORD": "secret",
        "EMAIL_FROM_ADDRESS": "no-reply@example.com",
        "EMAIL_FROM_NAME": "Workspace",
    }
    secure_call = mock_echo.confirm.call_args_list[-1]
    assert secure_call.kwargs["default"] is True
    assert mock_echo.prompt_until_valid.call_args_list[3].kwargs == {"password": True}


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_smtp_flags_given_are_kept_and_only_missing_are_asked(
    mock_echo: Mock, mock_interactive: Mock
) -> None:
    mock_echo.confirm.side_effect = [True, True, False]
    mock_echo.prompt_until_valid.side_effect = ["user", "secret", "no-reply@example.com"]
    mock_echo.prompt.return_value = ""
    passed: dict[str, str | None] = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": "2525", "SMTP_SECURE": "false"}

    prompt_optional_settings(passed, {})

    assert passed["SMTP_HOST"] == "smtp.example.com"
    assert passed["SMTP_PORT"] == "2525"
    assert passed["SMTP_SECURE"] == "false"
    assert passed["EMAIL_FROM_NAME"] is None
    assert "Configure sending e-mails (SMTP)?" not in [call.args[0] for call in mock_echo.confirm.call_args_list]


@mock.patch("deepfellow.workspace.utils.configure.is_interactive", return_value=True)
@mock.patch("deepfellow.workspace.utils.configure.echo")
def test_prompt_optional_settings_smtp_credentials_and_sender_from_flags_are_not_asked_again(
    mock_echo: Mock, mock_interactive: Mock
) -> None:
    mock_echo.confirm.side_effect = [True, True, False, False]
    mock_echo.prompt_until_valid.side_effect = ["smtp.example.com", 587]
    passed: dict[str, str | None] = {
        "SMTP_USERNAME": "user",
        "SMTP_PASSWORD": "secret",
        "EMAIL_FROM_ADDRESS": "no-reply@example.com",
        "EMAIL_FROM_NAME": "Workspace",
    }

    prompt_optional_settings(passed, {})

    assert passed["SMTP_HOST"] == "smtp.example.com"
    assert passed["SMTP_PORT"] == "587"
    assert passed["SMTP_SECURE"] == "false"
    assert passed["SMTP_USERNAME"] == "user"
    assert passed["SMTP_PASSWORD"] == "secret"
    assert passed["EMAIL_FROM_NAME"] == "Workspace"
    assert mock_echo.prompt_until_valid.call_count == 2
    assert mock_echo.prompt.call_count == 0
