# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""List the Docker image versions available for a service or model."""

from typing import Any

from deepfellow.common.echo import echo
from deepfellow.infra.utils.update_spec import DockerTags, fetch_docker_tags


def show_versions(
    server: str, api_key: str, service_id: str, installed: dict[str, Any] | None, model_id: str | None = None
) -> None:
    """Print the available image tags, newest first, marking the installed, newest, and default ones.

    Args:
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: Service id (e.g. "custom").
        installed: Current settings of the installed entry, or `None` when it isn't installed.
        model_id: Model id, for a model that has its own Docker image.
    """
    tags = fetch_docker_tags(server, api_key, service_id, installed, model_id)
    current = (installed or {}).get("image_version")
    echo.info("\n".join([f"image: {tags.image}", *(_format_tag(tag, tags, current) for tag in tags.tags)]))
    if warning := tags.cuda_warning:
        echo.warning(warning)


def _format_tag(tag: str, tags: DockerTags, current: str | None) -> str:
    """Format one tag with its markers, e.g. `v2.4.0 (newest, default)`."""
    markers = [
        name
        for name, applies in (
            ("installed", tag == current),
            ("newest", tag == tags.newest),
            ("default", tag == tags.default),
        )
        if applies
    ]
    suffix = f" ({', '.join(markers)})" if markers else ""
    return f"- {tag}{suffix}"
