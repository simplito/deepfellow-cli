# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Interactive questions about the optional Workspace settings."""

from collections.abc import Callable, Mapping, MutableMapping

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.install import resolve_admin_creds
from deepfellow.common.validation import (
    validate_email,
    validate_mongo_url,
    validate_port,
    validate_redis_url,
    validate_truthy,
)

ADMIN_KEYS = ("BOOTSTRAP_ADMIN_NAME", "BOOTSTRAP_ADMIN_EMAIL", "BOOTSTRAP_ADMIN_PASSWORD")
# The app refuses to start when any of the SMTP_TRIGGER_KEYS is set without all of the SMTP_REQUIRED_KEYS.
# SMTP_PORT and SMTP_SECURE alone do not configure e-mail.
SMTP_REQUIRED_KEYS = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM_ADDRESS")
SMTP_TRIGGER_KEYS = (*SMTP_REQUIRED_KEYS, "EMAIL_FROM_NAME")
SMTP_KEYS = (*SMTP_TRIGGER_KEYS, "SMTP_PORT", "SMTP_SECURE")
_DEFAULT_SMTP_PORT = "587"
_SMTP_SECURE_PORT = "465"

Passed = MutableMapping[str, str | None]


def _ask_external_service(
    passed: Passed,
    key: str,
    question: str,
    url_label: str,
    validation: Callable[[str | None], str | None],
) -> None:
    """Ask whether to run the service locally and, if not, for the URL of an existing one."""
    if passed.get(key):
        return
    if echo.confirm(question, default=True, ignore_yes=True):
        return
    passed[key] = echo.prompt_until_valid(url_label, validation)


def _ask_admin(passed: Passed) -> None:
    """Ask for the initial admin account; whatever was already given is not asked again."""
    if not any(passed.get(key) for key in ADMIN_KEYS) and not echo.confirm(
        "Create an initial admin account?", default=True, ignore_yes=True
    ):
        return
    name, email, password = resolve_admin_creds(
        passed.get("BOOTSTRAP_ADMIN_NAME"), passed.get("BOOTSTRAP_ADMIN_EMAIL"), passed.get("BOOTSTRAP_ADMIN_PASSWORD")
    )
    passed["BOOTSTRAP_ADMIN_NAME"] = name
    passed["BOOTSTRAP_ADMIN_EMAIL"] = email
    passed["BOOTSTRAP_ADMIN_PASSWORD"] = password


def _ask_smtp(passed: Passed) -> None:
    """Ask for the SMTP settings; whatever was already given is not asked again."""
    if not any(passed.get(key) for key in SMTP_KEYS) and not echo.confirm(
        "Configure sending e-mails (SMTP)?", default=False, ignore_yes=True
    ):
        return
    if not passed.get("SMTP_HOST"):
        passed["SMTP_HOST"] = echo.prompt_until_valid("SMTP host", validate_truthy)
    if not passed.get("SMTP_PORT"):
        passed["SMTP_PORT"] = str(
            echo.prompt_until_valid("SMTP port", validate_port, default=_DEFAULT_SMTP_PORT, original_default=None)
        )
    if not passed.get("SMTP_SECURE"):
        secure = echo.confirm(
            "Use TLS from the start of the connection (usually for port 465, not 587)?",
            default=passed["SMTP_PORT"] == _SMTP_SECURE_PORT,
            ignore_yes=True,
        )
        passed["SMTP_SECURE"] = str(secure).lower()
    if not passed.get("SMTP_USERNAME"):
        passed["SMTP_USERNAME"] = echo.prompt_until_valid("SMTP username", validate_truthy)
    if not passed.get("SMTP_PASSWORD"):
        passed["SMTP_PASSWORD"] = echo.prompt_until_valid("SMTP password", validate_truthy, password=True)
    if not passed.get("EMAIL_FROM_ADDRESS"):
        passed["EMAIL_FROM_ADDRESS"] = echo.prompt_until_valid("Sender e-mail address", validate_email)
    if not passed.get("EMAIL_FROM_NAME"):
        passed["EMAIL_FROM_NAME"] = echo.prompt("Sender name (optional)", default="") or None


def prompt_optional_settings(passed: Passed, existing: Mapping[str, str]) -> None:
    """Ask about the optional settings that were not given as flags, in interactive mode only.

    A reinstall over an existing `.env` keeps its configuration and asks nothing here; change it with flags.

    Args:
        passed: Values given explicitly, keyed by .env name. Answers are stored in it.
        existing: The .env of a previous install in the directory (empty on a fresh install).
    """
    if existing or not is_interactive():
        return
    _ask_external_service(
        passed,
        "MONGO_DB_URL",
        "Install a local MongoDB for DeepFellow Workspace?",
        "MongoDB connection URL (a replica set is required)",
        validate_mongo_url,
    )
    _ask_external_service(
        passed,
        "REDIS_URL",
        "Install a local Redis for DeepFellow Workspace?",
        "Redis URL",
        validate_redis_url,
    )
    _ask_admin(passed)
    _ask_smtp(passed)
