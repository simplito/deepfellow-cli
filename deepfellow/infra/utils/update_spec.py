# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Shared helpers for updating an installed service or model with changed settings."""

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

import typer

from deepfellow.common.echo import echo, is_interactive
from deepfellow.common.registry import newest_semver_tag, split_release_tag
from deepfellow.common.rest import get
from deepfellow.common.state import state
from deepfellow.infra.utils.connection import call_infra, is_installed, quote_id
from deepfellow.infra.utils.fields import parse_set_args, parse_spec_json

IMAGE_VERSION_FIELD = "image_version"


def installed_spec(installed: Any, name: str) -> dict[str, Any]:
    """Return the settings an installed service or model runs with.

    Args:
        installed: The raw `installed` value of a service or model entry (a service reports its
            settings directly, a model reports them under `spec`).
        name: Name used in the error message.

    Returns:
        A copy of the current settings.

    Raises:
        typer.Exit: If the entry is not installed or reports no settings.
    """
    if not is_installed(installed):
        echo.error(f"'{name}' is not installed. Install it first.")
        raise typer.Exit(1)
    # A model installed with default settings reports no spec at all.
    is_model = isinstance(installed, dict) and "registration_id" in installed
    spec = (installed.get("spec") or {}) if is_model else installed
    if not isinstance(spec, dict) or "stage" in spec:
        echo.error(f"'{name}' is still installing or reports no settings. Try again when it is installed.")
        raise typer.Exit(1)
    return dict(spec)


def build_updated_spec(
    current: dict[str, Any],
    spec: str | None,
    set_args: list[str] | None,
    image_version: str | None,
) -> dict[str, Any]:
    """Merge the requested changes into the current settings.

    Infra replaces the settings of a service or model as a whole when it updates one, so the result
    keeps every current value and overrides only what was requested. Nested maps (e.g. `envs`,
    `headers`) are merged key by key, so `--spec '{"envs": {"NEW": "1"}}'` adds a variable and keeps
    the others; any other value replaces the current one.

    Args:
        current: The settings the entry runs with now.
        spec: JSON object with the changed settings, as an alternative to `--set`.
        set_args: `key=value` overrides of individual settings.
        image_version: Docker image tag, shorthand for `--set image_version=<tag>`.

    Returns:
        The full settings to send to Infra.

    Raises:
        typer.Exit: If nothing is requested, or `--spec` is combined with `--set`.
    """
    if spec is not None and set_args:
        echo.error("--spec and --set cannot be used together. Use one or the other.")
        raise typer.Exit(1)
    changes: dict[str, Any] = parse_spec_json(spec) if spec is not None else dict(parse_set_args(set_args or []))
    if image_version is not None:
        changes[IMAGE_VERSION_FIELD] = image_version
    return _merge(current, changes)


def _merge(current: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Return `current` with `changes` applied, merging nested dicts recursively."""
    merged = dict(current)
    for key, value in changes.items():
        existing = merged.get(key)
        merged[key] = _merge(existing, value) if isinstance(existing, dict) and isinstance(value, dict) else value
    return merged


@dataclass
class DockerTags:
    """Docker image tags Infra offers for a service or model."""

    image: str
    tags: list[str] = field(default_factory=list[str])
    default: str | None = None
    """Tag Infra installs when no version is chosen."""
    installed: str | None = None
    """Tag the entry runs now, if it is installed."""
    infra_newest: str | None = None
    """Newest tag Infra picked for the installed variant (it knows each service's tag formats)."""
    infra_picks_newest: bool = False
    """Whether Infra reported `newest` at all; an Infra older than this field leaves the choice to the CLI."""
    needs_cuda: dict[str, str] | None = None
    """A newer tag held back by the host's NVIDIA driver: its `tag`, `required_cuda` and the `host_cuda`."""

    @property
    def newest(self) -> str | None:
        """The newest tag of the installed tag's variant, e.g. `-cu128`, `-rocm` or `-volta`.

        Infra chooses it, so tags such as llama.cpp's `server-vulkan-b10902` and a CUDA build that may move to
        the driver's CUDA version are handled. For an Infra that doesn't report it, the newest release within
        the installed tag's suffix is used; without an installed tag, or with one that isn't a release, only
        plain releases are considered.
        """
        if self.infra_picks_newest:
            return self.infra_newest
        parsed = split_release_tag(self.installed) if self.installed else None
        return newest_semver_tag(self.tags, parsed[1] if parsed else "")

    @property
    def cuda_warning(self) -> str | None:
        """Tell that a newer version exists but needs a newer CUDA than the host's driver supports."""
        if not self.needs_cuda:
            return None
        return (
            f"{self.needs_cuda['tag']} is newer but needs CUDA {self.needs_cuda['required_cuda']}, and the NVIDIA "
            f"driver on this host supports CUDA {self.needs_cuda['host_cuda']}. "
            "Update the NVIDIA driver to be able to use it."
        )


def fetch_docker_tags(
    server: str, api_key: str, service_id: str, current: dict[str, Any] | None, model_id: str | None = None
) -> DockerTags:
    """Fetch the tags Infra offers for a service or model, filtered for the hardware it runs on.

    Args:
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: Service id (e.g. "custom", or "ollama|cpu" for an instance).
        current: Current settings of the installed entry, or `None` when it isn't installed.
        model_id: Model id, for a model that has its own Docker image.

    Returns:
        The tags, newest release first.

    Raises:
        typer.Exit: If the registry cannot be reached.
    """
    query: dict[str, str] = {}
    # A stored `False` (older installs) is a hardware value too; dropping it makes Infra assume a GPU.
    if current and current.get("hardware") is not None:
        query["hardware"] = str(current["hardware"])
    if model_id:
        query["model_id"] = model_id
    # Infra keeps the variant of the installed tag (e.g. `-rocm`) when it picks the newest one.
    if current and current.get(IMAGE_VERSION_FIELD):
        query["current"] = str(current[IMAGE_VERSION_FIELD])
    url = f"{server}/admin/services/{quote_id(service_id)}/docker-tags"
    if query:
        url += f"?{urlencode(query)}"
    data = call_infra(
        lambda: get(url, api_key, item_name="Docker image tags", reraise=True),
        "Unable to fetch Docker image tags.",
        server=server,
        api_key=api_key,
        quiet=True,
    )
    if data.get("registry_unavailable") or not data.get("tags"):
        echo.error("Infra cannot list Docker image versions right now. Check its connection to the registry.")
        raise typer.Exit(1)
    return DockerTags(
        image=data.get("image", ""),
        tags=list(data["tags"]),
        default=data.get("default"),
        installed=(current or {}).get(IMAGE_VERSION_FIELD),
        infra_newest=data.get("newest"),
        infra_picks_newest="newest" in data,
        needs_cuda=data.get("newest_needs_cuda"),
    )


def resolve_image_version(
    requested: str | None,
    other_changes: bool,
    server: str,
    api_key: str,
    service_id: str,
    current: dict[str, Any],
    fields: list[dict[str, Any]],
    model_id: str | None = None,
) -> str | None:
    """Decide which Docker image tag the update moves to.

    A tag given by the user wins. Without one, the newest version of the installed variant is chosen, with a
    warning if a newer one needs a newer CUDA than the host supports, unless the user asked for other changes
    only, in which case the image stays as it is.

    Args:
        requested: Tag from `--image-version`.
        other_changes: Whether `--set` or `--spec` was given.
        server: Infra server URL.
        api_key: Infra admin API key.
        service_id: Service id (e.g. "custom").
        current: Current settings of the installed entry.
        fields: Setting fields the service or model declares; one must be a `docker-tags` field to
            have an image version of its own.
        model_id: Model id, for a model that has its own Docker image.

    Returns:
        The tag to use, or `None` to leave the image untouched.

    Raises:
        typer.Exit: If the entry has no image version setting, or no tag can be chosen.
    """
    if requested is None and other_changes:
        return None
    name = model_id or service_id
    if not any(item.get("type") == "docker-tags" for item in fields):
        # Infra offers the service's tags for a model too, but writing one into the model's settings changes nothing.
        echo.error(f"'{name}' has no Docker image version setting. Change its settings with --set or --spec.")
        raise typer.Exit(1)
    if requested is not None:
        return requested
    tags = fetch_docker_tags(server, api_key, service_id, current, model_id)
    if warning := tags.cuda_warning:
        echo.warning(warning)
    newest = tags.newest
    if newest is None:
        echo.error(
            f"Infra lists no release version matching the installed one of '{name}'. "
            "Choose one with --image-version; `versions` lists the tags."
        )
        raise typer.Exit(1)
    return newest


def _version_change_warning(old_tag: str | None, new_tag: str | None) -> str | None:
    """Describe a downgrade or a changed variant, or return `None` if the move looks like an upgrade."""
    old_parsed = split_release_tag(old_tag) if old_tag else None
    new_parsed = split_release_tag(new_tag) if new_tag else None
    if not old_parsed or not new_parsed:
        return None
    if old_parsed[1] != new_parsed[1]:
        old_variant, new_variant = old_parsed[1] or "plain", new_parsed[1] or "plain"
        return f"{new_tag} is a different variant than {old_tag} ({old_variant} -> {new_variant})"
    if new_parsed[0] < old_parsed[0]:
        return f"{new_tag} is older than {old_tag}"
    return None


def confirm_version_change(name: str, current: dict[str, Any], new: dict[str, Any]) -> bool:
    """Show the image tag change and ask for confirmation, unless `--yes` was given.

    Warns about a downgrade or a changed variant (e.g. dropping `-volta`) and then defaults to "no".

    Raises:
        typer.Exit: If the tag changes in non-interactive mode without `--yes`.
    """
    old_tag, new_tag = current.get(IMAGE_VERSION_FIELD), new.get(IMAGE_VERSION_FIELD)
    if old_tag == new_tag:
        return True
    warning = _version_change_warning(old_tag, new_tag)
    if warning:
        echo.warning(warning)
    if state.yes:
        return True
    if not is_interactive():
        echo.error("The update changes the image version. Pass --yes to apply it without asking.")
        raise typer.Exit(1)
    return echo.confirm(
        f"Update '{name}' from {old_tag or 'the bundled version'} to {new_tag}?", default=warning is None
    )
