"""REST utils."""

import typer

from deepfellow.common.echo import echo
from deepfellow.common.validation import validate_url


def get_infra_url(default: str | None) -> str:
    """Return infra URL. Repeat until a valid URL is provided."""
    server = ""
    while not server:
        try:
            server = echo.prompt("Provide DeepFellow Infra URL", default=default, validation=validate_url)
        except typer.BadParameter:
            echo.error("Invalid Deepfellow Infra address. Please try again.")

    return server
