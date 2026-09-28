# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Helpers for the DeepFellow Server's storage directory."""

from deepfellow.common.defaults import DF_SERVER_STORAGE_DIRECTORY


def config_json_exists() -> bool:
    """Best-effort check for whether config.json has already been seeded in the server's storage.

    The server has no `--storage` option to relocate its storage per install - unlike `infra
    install`, which exposes `--storage`/`DF_INFRA_STORAGE_DIR` and persists the choice in that
    install's own `.env` - so this is always the one fixed `DF_SERVER_STORAGE_DIRECTORY` shared by
    every server install on the machine, and no `.env` lookup is needed to locate it.

    Returns:
        True if config.json is present in the server's storage directory.
    """
    return (DF_SERVER_STORAGE_DIRECTORY / "config.json").is_file()
