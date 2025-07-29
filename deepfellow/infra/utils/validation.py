"""Validate infra data."""

from typing import Any

from deepfellow.common.exceptions import ConfigValidationError


def validate_config(config: dict[str, Any]) -> None:
    """Validate config retrieved from file.

    Raises:
        ConfigValidationError if config is failing
    """
    if not config:
        raise ConfigValidationError("No config provided. Please run `deepfellow infra configure`")
