# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

import pytest
import typer

from deepfellow.common.exceptions import InstallError
from deepfellow.common.state import state
from deepfellow.workspace.utils.webhook import (
    NO_WEBHOOK_WARNING,
    WEBHOOK_SECRET_KEY,
    _find_endpoint,
    _register,
    _remove_old_endpoint,
    configure_webhook,
    is_public_https,
    remove_webhook,
    webhook_url,
)

_MODULE = "deepfellow.workspace.utils.webhook"
_URL = "https://workspace.example.com/webhooks/df-server"
_HEADERS = {"OpenAI-Organization": "org"}


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://workspace.example.com", True),
        ("https://workspace.example.com:8443", True),
        ("https://8.8.8.8", True),
        ("http://workspace.example.com", False),
        ("https://localhost", False),
        ("https://127.0.0.1", False),
        ("https://192.168.1.10", False),
        ("https://10.0.0.5:3000", False),
        ("https://my-host", True),
        ("https://workspace.internal", True),
        ("https://workspace.local:3000", True),
        ("https://localhost.", False),
        ("https://app.localhost", False),
        ("https://10.0.0.1.", False),
        ("https://127.1", False),
        ("https://0x7f.1", False),
        ("https://2130706433", False),
        ("https://0.0.0.0", False),
        ("https://[::1]", False),
        ("https://[fe80::1]", False),
        ("https://[::ffff:10.0.0.1]", False),
    ],
)
def test_is_public_https_accepts_only_public_https_addresses(url: str, expected: bool) -> None:
    result = is_public_https(url)

    assert result is expected


@pytest.mark.parametrize("public_url", ["https://workspace.example.com", "https://workspace.example.com/"])
def test_webhook_url_appends_the_workspace_path_once(public_url: str) -> None:
    result = webhook_url(public_url)

    assert result == _URL


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@pytest.mark.parametrize("public_url", ["http://localhost:3000", "http://workspace.example.com", "https://10.0.0.5"])
def test_configure_webhook_warns_and_skips_without_public_https(
    mock_register: Mock, mock_echo: Mock, public_url: str
) -> None:
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, public_url)

    assert mock_echo.warning.call_args == mock.call(NO_WEBHOOK_WARNING)
    assert mock_register.call_count == 0
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
def test_configure_webhook_warns_and_skips_without_ids(mock_register: Mock, mock_echo: Mock) -> None:
    passed: dict[str, str | None] = {}

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_echo.warning.call_count == 1
    assert mock_register.call_count == 0
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_registers_generated_secret_and_stores_it(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, "https://workspace.example.com")

    secret = passed[WEBHOOK_SECRET_KEY]
    assert secret
    assert mock_register.call_args == mock.call("https://df.example.com", "token", "org", "proj", _URL, secret)


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_keeps_secret_and_ids_from_previous_install(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    passed: dict[str, str | None] = {}
    existing = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj", WEBHOOK_SECRET_KEY: "old"}

    configure_webhook(passed, existing, "https://workspace.example.com")

    assert passed[WEBHOOK_SECRET_KEY] == "old"
    assert mock_register.call_args == mock.call("https://df.example.com", "token", "org", "proj", _URL, "old")


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register", side_effect=typer.Exit(1))
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_warns_and_leaves_secret_unset_when_server_refuses(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_echo.warning.call_count == 1
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.get_token", side_effect=typer.Exit(1))
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_warns_when_login_fails(mock_server: Mock, mock_token: Mock, mock_echo: Mock) -> None:
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_echo.warning.call_count == 1
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token")
def test_configure_webhook_with_yes_warns_and_skips_without_stored_login(
    mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    state.yes = True
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_echo.warning.call_count == 1
    assert mock_token.call_count == 0
    assert mock_register.call_count == 0
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url")
@mock.patch(f"{_MODULE}.check_health")
def test_configure_webhook_with_yes_registers_on_workspace_server_without_default_prompt(
    mock_health: Mock, mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    state.yes = True
    state.cli_secrets_file.write_text("DF_USER_TOKEN=abc\n")
    passed: dict[str, str | None] = {
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
        "DF_SERVER_URL": "https://df.example.com/v1",
    }

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_server.call_count == 0
    assert mock_health.call_args == mock.call("https://df.example.com")
    secret = passed[WEBHOOK_SECRET_KEY]
    assert mock_register.call_args == mock.call("https://df.example.com", "token", "org", "proj", _URL, secret)


@mock.patch(f"{_MODULE}.post")
@mock.patch(f"{_MODULE}.rest_get", return_value={"data": [{"id": "e1", "url": "https://other.example.com/x"}]})
def test_register_creates_endpoint_when_none_has_the_address(mock_get: Mock, mock_post: Mock) -> None:
    _register("https://df.example.com", "token", "org", "proj", _URL, "secret")

    assert mock_post.call_args == mock.call(
        "https://df.example.com/v1/organization/projects/proj/webhooks",
        "token",
        headers=_HEADERS,
        item_name="webhook endpoint",
        data={"url": _URL, "secret": "secret"},
    )


@mock.patch(f"{_MODULE}.make_request")
@mock.patch(f"{_MODULE}.post")
@mock.patch(f"{_MODULE}.rest_get")
def test_register_rotates_secret_of_endpoint_found_on_a_later_page(
    mock_get: Mock, mock_post: Mock, mock_request: Mock
) -> None:
    mock_get.side_effect = [
        {"data": [{"id": "e1", "url": "https://other.example.com/x"}], "has_more": True, "last_id": "e1"},
        {"data": [{"id": "e2", "url": _URL}], "has_more": False, "last_id": "e2"},
    ]

    _register("https://df.example.com", "token", "org", "proj", _URL, "secret")

    assert mock_post.call_count == 0
    assert mock_get.call_args_list[1].args[0].endswith("?limit=100&after=e1")
    assert mock_request.call_args == mock.call(
        "PUT",
        "https://df.example.com/v1/organization/projects/proj/webhooks/e2",
        "token",
        headers=_HEADERS,
        data={"secret": "secret"},
        err_msg="Unable to update the webhook endpoint.",
    )


@mock.patch(f"{_MODULE}.rest_get")
def test_find_endpoint_url_encodes_the_page_cursor(mock_get: Mock) -> None:
    mock_get.side_effect = [
        {"data": [], "has_more": True, "last_id": "a&b=c"},
        {"data": [], "has_more": False},
    ]

    _find_endpoint("https://df.example.com", "token", _HEADERS, "proj", _URL)

    assert mock_get.call_args_list[1].args[0].endswith("?limit=100&after=a%26b%3Dc")


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}.echo")
@mock.patch(
    f"{_MODULE}.rest_get", return_value={"data": [{"id": "e1", "url": "https://old.example.com/webhooks/df-server"}]}
)
def test_remove_old_endpoint_deletes_endpoint_of_previous_address(
    mock_get: Mock, mock_echo: Mock, mock_delete: Mock
) -> None:
    mock_echo.confirm.return_value = True

    _remove_old_endpoint("https://df.example.com", "token", "org", "proj", "https://old.example.com/webhooks/df-server")

    assert mock_delete.call_args == mock.call(
        "https://df.example.com/v1/organization/projects/proj/webhooks/e1",
        "token",
        headers=_HEADERS,
        item_name="webhook endpoint",
    )


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}.echo")
@mock.patch(
    f"{_MODULE}.rest_get", return_value={"data": [{"id": "e1", "url": "https://old.example.com/webhooks/df-server"}]}
)
def test_remove_old_endpoint_keeps_endpoint_when_not_confirmed(
    mock_get: Mock, mock_echo: Mock, mock_delete: Mock
) -> None:
    mock_echo.confirm.return_value = False

    _remove_old_endpoint("https://df.example.com", "token", "org", "proj", "https://old.example.com/webhooks/df-server")

    assert mock_delete.call_count == 0


@mock.patch(f"{_MODULE}._remove_old_endpoint")
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_removes_endpoint_of_previous_address(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock, mock_remove: Mock
) -> None:
    passed: dict[str, str | None] = {}
    existing = {
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
        "PUBLIC_URL": "https://old.example.com",
    }

    configure_webhook(passed, existing, "https://workspace.example.com")

    assert mock_remove.call_args == mock.call(
        "https://df.example.com", "token", "org", "proj", "https://old.example.com/webhooks/df-server"
    )


@mock.patch(f"{_MODULE}._remove_old_endpoint")
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_does_not_remove_endpoint_when_address_is_unchanged(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock, mock_remove: Mock
) -> None:
    existing = {
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
        "PUBLIC_URL": "https://workspace.example.com/",
    }

    configure_webhook({}, existing, "https://workspace.example.com")

    assert mock_remove.call_count == 0


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}.rest_get", return_value={"data": []})
def test_remove_old_endpoint_does_nothing_when_server_has_no_such_endpoint(mock_get: Mock, mock_delete: Mock) -> None:
    _remove_old_endpoint("https://df.example.com", "token", "org", "proj", "https://old.example.com/webhooks/df-server")

    assert mock_delete.call_count == 0


@mock.patch(f"{_MODULE}._remove_old_endpoint", side_effect=typer.Exit(1))
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_keeps_secret_and_warns_when_old_endpoint_removal_fails(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock, mock_remove: Mock
) -> None:
    passed: dict[str, str | None] = {}
    existing = {
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
        "PUBLIC_URL": "https://old.example.com",
    }

    configure_webhook(passed, existing, "https://workspace.example.com")

    assert passed[WEBHOOK_SECRET_KEY]
    assert mock_echo.warning.call_count == 1


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_prefers_passed_secret_over_existing(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    passed: dict[str, str | None] = {WEBHOOK_SECRET_KEY: "passed"}
    existing = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj", WEBHOOK_SECRET_KEY: "old"}

    configure_webhook(passed, existing, "https://workspace.example.com")

    assert passed[WEBHOOK_SECRET_KEY] == "passed"
    assert mock_register.call_args == mock.call("https://df.example.com", "token", "org", "proj", _URL, "passed")


@pytest.mark.parametrize(
    ("df_server_url", "expected"),
    [
        ("https://df.example.com/v1", "https://df.example.com"),
        ("https://df.example.com/v1/", "https://df.example.com"),
        ("https://df.example.com/", "https://df.example.com"),
    ],
)
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
def test_configure_webhook_uses_the_server_workspace_talks_to(
    mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock, df_server_url: str, expected: str
) -> None:
    passed: dict[str, str | None] = {
        "DF_SERVER_URL": df_server_url,
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
    }

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_server.call_args == mock.call(expected)


@pytest.mark.parametrize("error", [ValueError("not json"), KeyError("id")])
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
@mock.patch(f"{_MODULE}._register")
def test_configure_webhook_warns_instead_of_aborting_on_malformed_server_response(
    mock_register: Mock, mock_server: Mock, mock_token: Mock, mock_echo: Mock, error: Exception
) -> None:
    mock_register.side_effect = error
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    configure_webhook(passed, {}, "https://workspace.example.com")

    assert mock_echo.warning.call_count == 1
    assert WEBHOOK_SECRET_KEY not in passed


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
def test_configure_webhook_warns_about_previous_endpoint_when_new_address_is_not_public(
    mock_register: Mock, mock_echo: Mock
) -> None:
    existing = {"PUBLIC_URL": "https://old.example.com"}

    configure_webhook({}, existing, "http://localhost:3000")

    assert mock_echo.warning.call_count == 2
    assert "https://old.example.com" in mock_echo.warning.call_args.args[0]
    assert mock_register.call_count == 0


@mock.patch(f"{_MODULE}.rest_get")
def test_find_endpoint_stops_when_has_more_is_set_without_last_id(mock_get: Mock) -> None:
    mock_get.return_value = {"data": [], "has_more": True}

    result = _find_endpoint("https://df.example.com", "token", _HEADERS, "proj", _URL)

    assert result is None
    assert mock_get.call_count == 1


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}.echo")
@mock.patch(
    f"{_MODULE}.rest_get", return_value={"data": [{"id": "e1", "url": "https://old.example.com/webhooks/df-server"}]}
)
def test_remove_old_endpoint_asks_even_with_yes(mock_get: Mock, mock_echo: Mock, mock_delete: Mock) -> None:
    mock_echo.confirm.return_value = False

    _remove_old_endpoint("https://df.example.com", "token", "org", "proj", "https://old.example.com/webhooks/df-server")

    assert mock_echo.confirm.call_args.kwargs == {"ignore_yes": True}
    assert mock_delete.call_count == 0


_PRUNE_ENV = {
    "PUBLIC_URL": "https://ws.example.com",
    "DF_SERVER_ORGANIZATION_ID": "org1",
    "DF_SERVER_PROJECT_ID": "proj1",
}


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}._find_endpoint", return_value="e1")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
@mock.patch(f"{_MODULE}.echo")
def test_remove_webhook_deletes_the_endpoint_of_the_workspace(
    mock_echo: Mock, mock_server: Mock, mock_token: Mock, mock_find: Mock, mock_delete: Mock
) -> None:
    remove_webhook(_PRUNE_ENV)

    assert mock_find.call_args == mock.call(
        "https://df.example.com",
        "token",
        {"OpenAI-Organization": "org1"},
        "proj1",
        "https://ws.example.com/webhooks/df-server",
    )
    assert mock_delete.call_args == mock.call(
        "https://df.example.com/v1/organization/projects/proj1/webhooks/e1",
        "token",
        headers={"OpenAI-Organization": "org1"},
        item_name="webhook endpoint",
    )


@pytest.mark.parametrize(
    "env",
    [
        {},
        {**_PRUNE_ENV, "PUBLIC_URL": "http://localhost:3000"},
        {"PUBLIC_URL": "https://ws.example.com"},
    ],
)
@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}.get_server_url")
def test_remove_webhook_does_nothing_without_public_https_or_ids(
    mock_server: Mock, mock_delete: Mock, env: dict[str, str]
) -> None:
    remove_webhook(env)

    assert mock_server.call_count == 0
    assert mock_delete.call_count == 0


@mock.patch(f"{_MODULE}.delete")
@mock.patch(f"{_MODULE}._find_endpoint", return_value=None)
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
@mock.patch(f"{_MODULE}.echo")
def test_remove_webhook_skips_delete_when_endpoint_is_missing(
    mock_echo: Mock, mock_server: Mock, mock_token: Mock, mock_find: Mock, mock_delete: Mock
) -> None:
    remove_webhook(_PRUNE_ENV)

    assert mock_delete.call_count == 0
    assert "no webhook endpoint" in mock_echo.info.call_args.args[0]


@mock.patch(f"{_MODULE}.get_token", side_effect=typer.Exit(1))
@mock.patch(f"{_MODULE}.get_server_url", return_value="https://df.example.com")
@mock.patch(f"{_MODULE}.echo")
def test_remove_webhook_warns_and_goes_on_when_login_fails(
    mock_echo: Mock, mock_server: Mock, mock_token: Mock
) -> None:
    remove_webhook(_PRUNE_ENV)

    assert "was not removed" in mock_echo.warning.call_args.args[0]


@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.get_server_url")
@mock.patch(f"{_MODULE}.check_health")
def test_configure_webhook_uses_cli_server_url_without_default_server_prompt(
    mock_health: Mock, mock_server: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock
) -> None:
    passed: dict[str, str | None] = {
        "DF_SERVER_URL": "http://server:8000/v1",
        "DF_SERVER_ORGANIZATION_ID": "org",
        "DF_SERVER_PROJECT_ID": "proj",
    }

    configure_webhook(passed, {}, "https://workspace.example.com", "http://localhost:8000")

    assert mock_server.call_count == 0
    assert mock_health.call_args == mock.call("http://localhost:8000")
    assert mock_register.call_args.args[0] == "http://localhost:8000"


@pytest.mark.parametrize("failure", [typer.Exit(1), ValueError("bad"), KeyError("k")])
@mock.patch(f"{_MODULE}.echo")
@mock.patch(f"{_MODULE}._register")
@mock.patch(f"{_MODULE}.get_token", return_value="token")
@mock.patch(f"{_MODULE}.check_health")
def test_configure_webhook_raises_when_setup_fails_for_a_caller_naming_the_cli_server(
    mock_health: Mock, mock_token: Mock, mock_register: Mock, mock_echo: Mock, failure: Exception
) -> None:
    mock_register.side_effect = failure
    passed: dict[str, str | None] = {"DF_SERVER_ORGANIZATION_ID": "org", "DF_SERVER_PROJECT_ID": "proj"}

    with pytest.raises(InstallError, match="--resume"):
        configure_webhook(passed, {}, "https://workspace.example.com", "http://localhost:8000")

    assert WEBHOOK_SECRET_KEY not in passed
