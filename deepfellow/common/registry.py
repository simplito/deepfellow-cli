# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Shared Docker image registry utilities."""

import re

import httpx
import typer

from deepfellow.common import version as cli_info
from deepfellow.common.echo import echo
from deepfellow.common.version import compatible_tags, is_compatible_with_cli, parse_major_minor


def _parse_tag(tag: str) -> tuple[int, ...] | None:
    """Return (major, minor, patch) for tags like 1.2.3 or v1.2.3, else None."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    return tuple(int(x) for x in match.groups()) if match else None


def _get_registry_token(registry: str, image_path: str) -> str | None:
    """Obtain an anonymous bearer token via the registry's WWW-Authenticate realm."""
    try:
        probe = httpx.get(f"https://{registry}/v2/", timeout=10)
        www_auth = probe.headers.get("www-authenticate", "")
        # parse: Bearer realm="...",service="...",scope="..."
        realm_match = re.search(r'realm="([^"]+)"', www_auth)
        service_match = re.search(r'service="([^"]+)"', www_auth)
        if not realm_match:
            echo.debug(f"registry auth: no WWW-Authenticate realm from {registry}")
            return None
        realm = realm_match.group(1)
        service = service_match.group(1) if service_match else ""
        params = {"scope": f"repository:{image_path}:pull"}
        if service:
            params["service"] = service
        token_resp = httpx.get(realm, params=params, timeout=10)
        token_resp.raise_for_status()
        data = token_resp.json()
        return data.get("token") or data.get("access_token")
    except Exception as exc:
        echo.debug(f"registry auth failed for {registry}: {exc}")
        return None


def list_image_tags(hub: str) -> list[str]:
    """Return the image's available tags from the registry, newest semver first.

    Args:
        hub: Image hub without tag, e.g. ``registry.example.com/org/image``.

    Returns an empty list if the registry is unreachable, anonymous auth fails, or it reports no
    tags at all - never raises, since this is used to offer choices, not required data.
    """
    parts = hub.split("/", 1)
    if len(parts) != 2:
        echo.debug(f"registry: cannot parse hub '{hub}' - no registry/path separator")
        return []
    registry, image_path = parts

    token = _get_registry_token(registry, image_path)
    if not token:
        echo.debug(f"registry auth: no token obtained for {hub}")
        return []

    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.get(
            f"https://{registry}/v2/{image_path}/tags/list",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        raw_tags: list[str] = resp.json().get("tags") or []
    except Exception as exc:
        echo.debug(f"registry tags request failed for {hub}: {exc}")
        return []

    semver_tags = sorted((t for t in raw_tags if _parse_tag(t)), key=lambda v: _parse_tag(v) or (0, 0, 0), reverse=True)
    other_tags = sorted(t for t in raw_tags if not _parse_tag(t))
    return semver_tags + other_tags


def split_release_tag(tag: str) -> tuple[tuple[int, ...], str] | None:
    """Split a tag like `v2.3.0-volta` into its version `(2, 3, 0)` and suffix `-volta`.

    Returns:
        The version and the suffix (empty for a plain release), or `None` if the tag doesn't start with
        a `X.Y.Z` version.
    """
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(-.+)?", tag)
    if not match:
        return None
    return (int(match[1]), int(match[2]), int(match[3])), match[4] or ""


def newest_semver_tag(tags: list[str], suffix: str = "") -> str | None:
    """Return the highest `1.2.3` or `v1.2.3` tag within one suffix family, or `None` if there is none.

    A suffix such as `-volta` or `-cu128` marks a variant of a release (hardware, prerelease), so tags
    are only compared with others that carry the same suffix.

    Args:
        tags: Tags to choose from.
        suffix: The suffix family to look in; empty for plain releases.
    """
    family = [(parsed[0], tag) for tag in tags if (parsed := split_release_tag(tag)) and parsed[1] == suffix]
    return max(family, key=lambda item: item[0], default=(None, None))[1]


def get_newest_image_tag(hub: str) -> str:
    """Return the full image reference with the newest semver tag from the registry.

    Args:
        hub: Image hub without tag, e.g. ``registry.example.com/org/image``.

    Only tags this CLI is compatible with are considered (see `is_compatible_with_cli`), so a CLI 1.x
    never picks up a 2.0 release.

    Raises:
        typer.Exit: If the registry is unreachable or has no release tags, or has release tags but none
            of them works with this CLI.
    """
    semver_tags = [t for t in list_image_tags(hub) if _parse_tag(t)]
    if not semver_tags:
        echo.error(
            f"Couldn't determine the newest release of {hub}: the registry is unreachable or has no release tags. "
            f"Pass a version explicitly: `--image {hub}:X.Y.Z` (or `--tag X.Y.Z` on update)."
        )
        raise typer.Exit(1)

    compatible = compatible_tags(semver_tags)
    if not compatible:
        echo.error(
            f"No version of {hub} is compatible with DeepFellow CLI {cli_info.cli_version()}. "
            "Run `deepfellow cli update` to update the CLI first."
        )
        raise typer.Exit(1)

    return f"{hub}:{compatible[0]}"


def _image_tag(image: str) -> str | None:
    """Return the tag of an image reference, or `None` if it has none.

    A digest (`@sha256:...`) is ignored, and only the last path segment is searched, so the port of a
    registry (`registry:5000/df/infra`) isn't mistaken for a tag.
    """
    last_segment = image.partition("@")[0].rpartition("/")[2]
    name, separator, tag = last_segment.partition(":")
    return tag if name and separator and tag else None


def warn_version_check_skipped() -> None:
    """Tell the user that the CLI/component compatibility checks were bypassed on purpose."""
    echo.warning("Skipping the CLI/component version compatibility check (--skip-version-check).")


def assert_cli_compatible(component: str, image: str) -> None:
    """Exit unless `image` carries a version this CLI is known to handle.

    Anything that can't be compared with the CLI's version (no tag, a tag that isn't a version, a digest, even one
    next to a tag) is refused as well: it needs an explicit `--skip-version-check`. A dev build of the CLI,
    whose own version can't be read, accepts every image.

    Args:
        component: Name for the message, e.g. ``Server``.
        image: Full image reference.

    Raises:
        typer.Exit: If the image's version is outside what the CLI supports, or can't be determined. The hint
            is to update the CLI for a newer release, and to pick a matching release for an older one.
    """
    cli = cli_info.cli_version()
    cli_parsed = parse_major_minor(cli)
    if cli_parsed is None:
        return
    # Docker pulls by digest and ignores a tag next to it, so the tag says nothing about what runs.
    tag = None if "@" in image else _image_tag(image)
    component_version = parse_major_minor(tag) if tag else None
    if component_version is None:
        echo.error(
            f"Can't tell whether {image} works with DeepFellow CLI {cli}: it has no version to compare. "
            f"Use an image with a version tag, or pass `--skip-version-check` to use it anyway."
        )
        raise typer.Exit(1)
    if is_compatible_with_cli(tag or ""):
        return
    # Updating the CLI only helps against a release newer than the CLI supports.
    hint = (
        "Use a release that matches the CLI, or pass `--skip-version-check`."
        if component_version < cli_parsed
        else "Run `deepfellow cli update` to update the CLI first, then retry, or pass `--skip-version-check`."
    )
    echo.error(
        f"DeepFellow {component} {(tag or '').removeprefix('v')} is not compatible with DeepFellow CLI {cli}. {hint}"
    )
    raise typer.Exit(1)


def require_local_image_tag(
    image: str | None,
    component: str = "",
    local_image_flag: str = "--local-image",
    image_hint: str = "`--image <name>:<tag>`",
) -> str:
    """Return the image of a `--local-image` run, exiting when it carries no explicit tag.

    A locally built image can't be looked up in the registry, so the tag must be named.

    Args:
        image: The image given to the command, `None` when none was.
        component: Name put in front of the message, e.g. ``Infra``; none when empty.
        local_image_flag: The flag of the calling command that selects a local image.
        image_hint: How the caller names an image with a tag, shown as the way to fix the error.

    Raises:
        typer.Exit: If `image` is missing or has no tag.
    """
    if image is None or _image_tag(image) is None or "@" in image:
        prefix = f"{component}: " if component else ""
        echo.error(
            f"{prefix}`{local_image_flag}` needs an explicit image tag, as a local build can't be matched to a "
            f"release: pass {image_hint}."
        )
        raise typer.Exit(1)
    return image


def resolve_install_image(
    component: str,
    hub: str,
    image: str | None,
    local_image: bool,
    skip_version_check: bool,
    local_image_flag: str = "--local-image",
    image_flag: str = "--image",
) -> str:
    """Validate the image of an install before anything is changed; return the image reference to install.

    Args:
        component: Name for the message, e.g. ``Server``.
        hub: Image hub without tag, where the newest release is looked up.
        image: The image given to the command, `None` when none was chosen.
        local_image: Whether a locally built image is used, which is never checked but needs an explicit tag.
        skip_version_check: Whether to bypass the compatibility check of an explicit image.
        local_image_flag: The caller's flag that selects a local image, named in the error.
        image_flag: The caller's flag that gives the image, named in the error.

    Returns:
        The image as given, or the newest compatible image reference when none was chosen.

    Raises:
        typer.Exit: If the registry has no release this CLI can install, the explicit image isn't compatible,
            or a local image has no tag.
    """
    if local_image:
        return require_local_image_tag(image, component, local_image_flag, f"`{image_flag} <name>:<tag>`")
    if image is None:
        return get_newest_image_tag(hub)
    if skip_version_check:
        warn_version_check_skipped()
    else:
        assert_cli_compatible(component, image)
    return image


def assert_not_downgrade(component: str, current: str, newest: str) -> None:
    """Exit when the newest release this CLI supports is older than what is already installed.

    Args:
        component: Name for the message, e.g. ``Server``.
        current: Installed image reference. One whose tag isn't a version passes.
        newest: Image reference picked for the update. One whose tag isn't a version passes.

    Raises:
        typer.Exit: If `newest` is older than `current`, so the update would silently downgrade.
    """
    installed_tag = current.rpartition(":")[2]
    newest_tag = newest.rpartition(":")[2]
    installed = _parse_tag(installed_tag)
    target = _parse_tag(newest_tag)
    if installed is None or target is None or target >= installed:
        return
    echo.error(
        f"Installed DeepFellow {component} {installed_tag.removeprefix('v')} is newer than "
        f"DeepFellow CLI {cli_info.cli_version()} supports (newest compatible: {newest_tag.removeprefix('v')}). "
        "Run `deepfellow cli update` to update the CLI, pass `--tag` to downgrade on purpose, "
        "or `--skip-version-check` to bypass this check."
    )
    raise typer.Exit(1)
