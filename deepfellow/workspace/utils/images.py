# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Image versions of the Workspace stack."""

from deepfellow.common.echo import echo
from deepfellow.common.registry import split_release_tag


def image_tag(image: str) -> str | None:
    """Return the tag of an image reference, ignoring a digest and a registry port.

    Args:
        image: Image reference, e.g. `mongo:8.2.12@sha256:...`.

    Returns:
        The tag, or `None` when the reference has none.
    """
    last_segment = image.partition("@")[0].rpartition("/")[2]
    name, separator, tag = last_segment.partition(":")
    return tag if name and separator and tag else None


def image_version(image: str) -> tuple[int, ...] | None:
    """Return the `X.Y.Z` version in the tag of an image reference.

    Args:
        image: Image reference.

    Returns:
        The version, or `None` when the tag is not a version.
    """
    tag = image_tag(image)
    parsed = split_release_tag(tag) if tag else None
    return parsed[0] if parsed else None


def choose_mongo_image(old: str, new: str) -> str:
    """Pick the Mongo image for an update, asking before a change of the major version.

    Mongo starts only on data written by the previous major version (with its feature compatibility version), so a
    different major, or one that cannot be read from the tag, needs the user's consent. The question is not answered
    by `--yes`, and the non-interactive default keeps the old image.

    Args:
        old: The Mongo image in the existing compose.yaml.
        new: The Mongo image pinned in the CLI.

    Returns:
        `new`, or `old` when the user declines the change.
    """
    if old == new:
        return new
    old_version, new_version = image_version(old), image_version(new)
    if old_version is not None and new_version is not None and old_version[0] == new_version[0]:
        return new
    echo.warning(
        f"This update changes the Mongo of DeepFellow Workspace from {old} to {new}, another major version (or one "
        "that cannot be told from the image tag). Mongo may then fail to start on the existing data; back up its "
        "Docker volume first."
    )
    if echo.confirm(f"Change the Mongo image to {new}?", default=False, ignore_yes=True):
        return new
    echo.info(f"Keeping the Mongo image {old}.")
    return old
