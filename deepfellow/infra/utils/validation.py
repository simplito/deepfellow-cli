"""Validate infra data."""

from typing import Any

from deepfellow.common.exceptions import ConfigValidationError

PLEASE_RUN_CONFIGURE = "Please run `deepfellow infra configure`."
REQUIRED_FIELDS = ("repository", "directory")


def validate_config(config: dict[str, Any]) -> None:
    """Validate config retrieved from file.

    Raises:
        ConfigValidationError if config is failing
    """
    if not config:
        raise ConfigValidationError(f"No config provided. {PLEASE_RUN_CONFIGURE}")

    if not all(config.get(field) is not None for field in REQUIRED_FIELDS):
        raise ConfigValidationError(f"Missing required fields in config file. {PLEASE_RUN_CONFIGURE}")
