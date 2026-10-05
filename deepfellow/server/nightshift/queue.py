# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""server nightshift queue typer command."""

from typing import Any

import typer

from deepfellow.common.echo import echo
from deepfellow.common.rest import get as http_get
from deepfellow.common.rest import get_server_url
from deepfellow.common.state import state
from deepfellow.common.validation import validate_server
from deepfellow.server.utils.login import get_token

app = typer.Typer()


def _format_queue_stats(stats: dict[str, Any] | None) -> str:
    """Render one queue's broker stats, or a placeholder for a queue the broker never created."""
    if stats is None:
        return "not created yet"
    return f"{stats['message_count']} message(s), {stats['consumer_count']} consumer(s)"


@app.command()
def queue(
    server: str | None = typer.Option(None, "--url", callback=validate_server, help="DeepFellow Server address"),
) -> None:
    """Show Nightshift's RabbitMQ queue backlog via GET /admin/queues.

    Read-only: displays `nightshift_enabled`, RabbitMQ connectivity, and per-queue message/consumer
    counts (including retry-tier queues) exactly as reported by the server, without assuming a
    fixed set of queue names - that's owned by the server and may change. There is deliberately no
    command here to purge or otherwise mutate a queue; use RabbitMQ's own management UI for that.
    """
    secrets_file = state.cli_secrets_file
    server_url = get_server_url(server)
    token = get_token(secrets_file, server_url)

    response = http_get(f"{server_url}/admin/queues", token, item_name="Nightshift queues")

    echo.info(f"nightshift_enabled: {response['nightshift_enabled']}")
    echo.info(f"connected: {response['connected']}")
    if not response["connected"]:
        return

    for group in response["queues"]:
        echo.info(f"\n{group['name']}: {_format_queue_stats(group['main'])}")
        for tier, retry in enumerate(group["retries"], start=1):
            echo.info(f"  retry {tier}: {_format_queue_stats(retry)}")
