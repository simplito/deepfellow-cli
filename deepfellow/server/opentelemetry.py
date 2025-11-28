"""infra connect command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import DF_OTEL_EXPORTER_OTLP_ENDPOINT
from deepfellow.common.echo import echo
from deepfellow.common.env import env_get, env_set
from deepfellow.common.system import run
from deepfellow.common.validation import validate_directory, validate_url
from deepfellow.server.utils.options import directory_option

app = typer.Typer()


@app.command()
def opentelemetry(
    directory: Path = directory_option(callback=validate_directory),
    otel_url: str | None = typer.Argument(
        None,
        envvar=DF_OTEL_EXPORTER_OTLP_ENDPOINT,
        help="Open Telemetry url (DF_OTEL_EXPORTER_OTLP_ENDPOINT).",
        callback=validate_url,
    ),
) -> None:
    """Connect to Open Telemetry."""
    env_file = directory / ".env"
    original_otel_url = env_get(env_file, "DF_OTEL_EXPORTER_OTLP_ENDPOINT")

    if original_otel_url:
        echo.info(f"Disconnecting from {original_otel_url} ...")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    original_env_content = read_env_file_to_dict(env_file)

    if not otel_url:
        otel_url = echo.prompt(
            "Provide OTL url",
            default=original_env_content.get(
                "df_otel_exporter_orlp_endpoint",
                str(original_env_content.get("df_otel_exporter_otlp_endpoint") or "http://localhost:4317"),
            ),
        )

    if otel_url:
        env_set(env_file, "DF_OTEL_EXPORTER_OTLP_ENDPOINT", otel_url, quiet=True)
        env_set(env_file, "DF_OTEL_TRACING_ENABLED", "true")

        echo.info("Restarting this instance DeepFellow Server ...")
        run("docker compose down", cwd=directory, quiet=True)
        run("docker compose up -d", cwd=directory, quiet=True)

        echo.success(f"DeepFellow Server is connected to Open Telemetry {otel_url}")

    else:
        echo.info("OpenTelemetry settings in DeepFellow remain the same as before")
