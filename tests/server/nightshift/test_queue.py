# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

from unittest import mock
from unittest.mock import Mock

from typer.testing import CliRunner

from deepfellow.server.nightshift.queue import app, queue

SERVER = "http://localhost:8000"

runner = CliRunner()


@mock.patch("deepfellow.server.nightshift.queue.echo")
@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_calls_admin_queues_endpoint(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_http_get.return_value = {"nightshift_enabled": True, "connected": True, "queues": []}

    queue(server=None)

    assert mock_http_get.call_count == 1
    assert mock_http_get.call_args == mock.call(f"{SERVER}/admin/queues", "dfuser_abc", item_name="Nightshift queues")


@mock.patch("deepfellow.server.nightshift.queue.echo")
@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_prints_response_generically_without_hardcoded_queue_names(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    mock_http_get.return_value = {
        "nightshift_enabled": True,
        "connected": True,
        "queues": [
            {
                "name": "a-brand-new-queue-type-not-in-any-hardcoded-list",
                "main": {
                    "name": "a-brand-new-queue-type-not-in-any-hardcoded-list",
                    "message_count": 3,
                    "consumer_count": 1,
                },
                "retries": [None],
            }
        ],
    }

    queue(server=None)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "nightshift_enabled: True" in info_messages
    assert "connected: True" in info_messages
    assert "\na-brand-new-queue-type-not-in-any-hardcoded-list: 3 message(s), 1 consumer(s)" in info_messages
    assert "  retry 1: not created yet" in info_messages


@mock.patch("deepfellow.server.nightshift.queue.echo")
@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_reports_queue_never_created_by_broker(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    """A queue that's never had a message published to it is reported as such, not as 0 messages -
    RabbitMQ never created it, so there is nothing to distinguish it from an empty-but-existing queue
    without a dedicated placeholder."""
    mock_http_get.return_value = {
        "nightshift_enabled": True,
        "connected": True,
        "queues": [{"name": "webhook_deliveries", "main": None, "retries": []}],
    }

    queue(server=None)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert "\nwebhook_deliveries: not created yet" in info_messages


@mock.patch("deepfellow.server.nightshift.queue.echo")
@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_skips_queue_listing_when_not_connected(
    mock_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
    mock_echo: Mock,
) -> None:
    """Nothing to list when RabbitMQ isn't connected - the server itself returns an empty `queues`
    list in that case, so there's no per-queue formatting to do."""
    mock_http_get.return_value = {"nightshift_enabled": True, "connected": False, "queues": []}

    queue(server=None)

    info_messages = [call.args[0] for call in mock_echo.info.call_args_list]
    assert info_messages == ["nightshift_enabled: True", "connected: False"]


@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_cli_leaves_url_unset_so_the_configured_server_is_used(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
) -> None:
    """Like every other server command, --url defaults to None: get_server_url() then falls back to
    the saved DF_SERVER_URL. A hardcoded localhost default ignored the saved server and, on a
    machine without one, silently saved localhost:8000 as the default for every command."""
    mock_http_get.return_value = {"nightshift_enabled": True, "connected": True, "queues": []}

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert mock_get_server_url.call_args == mock.call(None)


@mock.patch("deepfellow.server.nightshift.queue.http_get")
@mock.patch("deepfellow.server.nightshift.queue.get_token", return_value="dfuser_abc")
@mock.patch("deepfellow.server.nightshift.queue.get_server_url", return_value=SERVER)
def test_queue_cli_passes_an_explicit_url_to_get_server_url(
    mock_get_server_url: Mock,
    mock_get_token: Mock,
    mock_http_get: Mock,
) -> None:
    mock_http_get.return_value = {"nightshift_enabled": True, "connected": True, "queues": []}

    result = runner.invoke(app, ["--url", "http://example.com:9000/"])

    assert result.exit_code == 0
    assert mock_get_server_url.call_args == mock.call("http://example.com:9000")
