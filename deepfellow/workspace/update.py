# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Update workspace typer command."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import typer

from deepfellow.common.defaults import (
    DF_WORKSPACE_IMAGE,
    DF_WORKSPACE_IMAGE_HUB,
    MONGO_IMAGE,
    WORKSPACE_APP_SERVICE,
    WORKSPACE_MONGO_SERVICE,
    WORKSPACE_REDIS_IMAGE,
)
from deepfellow.common.docker import DockerError, get_running_service_image
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError
from deepfellow.common.install import assert_docker
from deepfellow.common.system import run
from deepfellow.workspace.utils.docker import offer_restart
from deepfellow.workspace.utils.images import choose_mongo_image, image_tag, image_version
from deepfellow.workspace.utils.install import (
    IMAGE_KEY,
    build_stack_compose,
    current_service_images,
    read_installed_env,
    write_stack,
)
from deepfellow.workspace.utils.options import directory_option
from deepfellow.workspace.utils.validation import check_workspace_directory

app = typer.Typer()


def _version(image: str) -> str:
    """Return the version shown to the user: the image tag without a leading `v`, or the whole reference."""
    tag = image_tag(image)
    return tag.removeprefix("v") if tag else image


def _assert_not_downgrade(current: str, target: str) -> None:
    """Exit when the installed Workspace is newer than the image pinned in this CLI.

    Args:
        current: The installed image.
        target: The image pinned in the CLI.

    Raises:
        typer.Exit: When `target` has an older version than `current`.
    """
    installed, pinned = image_version(current), image_version(target)
    if installed is None or pinned is None or pinned >= installed:
        return
    echo.error(
        f"Installed DeepFellow Workspace {_version(current)} is newer than this CLI supports ({_version(target)}). "
        "Run 'deepfellow cli update' to update the CLI, or pass --tag or --image to choose the version on purpose."
    )
    raise typer.Exit(1)


def _cli_service_images(old_images: Mapping[str, str]) -> dict[str, str]:
    """Return the images this CLI pins for the stack's own Mongo and Redis that the install has."""
    return {name: MONGO_IMAGE if name == WORKSPACE_MONGO_SERVICE else WORKSPACE_REDIS_IMAGE for name in old_images}


def _pull_images(compose: Mapping[str, Any]) -> None:
    """Pull every image of the new stack, so a failure leaves the installation untouched.

    Args:
        compose: The compose dict of the updated stack.

    Raises:
        typer.Exit: When an image cannot be pulled.
    """
    for service in compose["services"].values():
        image = service["image"]
        try:
            run(["docker", "pull", image], raises=DockerError)
        except DockerError as exc:
            echo.error(f"Could not pull {image}; nothing was changed.")
            raise typer.Exit(1) from exc


@app.command()
def update(
    directory: Path = directory_option(),
    image: str | None = typer.Option(
        None, envvar="DF_WORKSPACE_IMAGE", help=f"DeepFellow Workspace image. Default: {DF_WORKSPACE_IMAGE}."
    ),
    tag: str | None = typer.Option(
        None, help=f"DeepFellow Workspace image tag (e.g. v0.7.1) on {DF_WORKSPACE_IMAGE_HUB}."
    ),
) -> None:
    """Update DeepFellow Workspace; its secrets, data and settings are kept."""
    if image and tag:
        raise typer.BadParameter("Only one of --image and --tag can be given.")
    check_workspace_directory(directory)
    assert_docker()
    existing = read_installed_env(directory)

    current = existing.get(IMAGE_KEY, "")
    target = image or (f"{DF_WORKSPACE_IMAGE_HUB}:{tag}" if tag else DF_WORKSPACE_IMAGE)
    if not image and not tag:
        _assert_not_downgrade(current, target)
    try:
        old_images = current_service_images(directory)
    except InstallError as exc:
        echo.error(str(exc))
        raise typer.Exit(1) from exc
    images = _cli_service_images(old_images)
    if WORKSPACE_MONGO_SERVICE in old_images:
        images[WORKSPACE_MONGO_SERVICE] = choose_mongo_image(old_images[WORKSPACE_MONGO_SERVICE], MONGO_IMAGE)
    # Compared with the images chosen above, so a declined Mongo move does not count as a pending update.
    if (
        current == target
        and images == old_images
        and get_running_service_image(WORKSPACE_APP_SERVICE, directory) == target
    ):
        echo.success(f"DeepFellow Workspace is already up to date ({_version(target)}).")
        return

    env = {**existing, IMAGE_KEY: target}
    try:
        compose = build_stack_compose(env, images)
    except InstallError as exc:
        echo.error(str(exc))
        raise typer.Exit(1) from exc
    _pull_images(compose)
    try:
        write_stack(directory, env, images=images)
    except InstallError as exc:
        echo.error(str(exc))
        raise typer.Exit(1) from exc
    echo.success(f"DeepFellow Workspace updated to {_version(target)}.")
    offer_restart(directory, "update")
