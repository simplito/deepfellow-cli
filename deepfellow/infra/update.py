# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import (
    read_env_file_to_dict,
)
from deepfellow.common.defaults import DF_INFRA_IMAGE, DF_INFRA_IMAGE_HUB, DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.docker import get_running_service_image, load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.system import run
from deepfellow.infra.utils.docker import start_infra, stop_infra
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


def _resolve_image(image: str, tag: str | None, current: str = "") -> str:
    """Return the final image reference to use for update."""
    if tag:
        return f"{DF_INFRA_IMAGE_HUB}:{tag}"
    if image == DF_INFRA_IMAGE:
        newest = get_newest_image_tag(DF_INFRA_IMAGE_HUB)
        if newest != current:
            echo.info(f"Newest image: {newest}")
        return newest
    return image


@app.command()
def update(
    directory: Path = directory_option(exists=True),
    image: str = typer.Option(DF_INFRA_IMAGE, envvar="DF_INFRA_IMAGE", help="DeepFellow Infra docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Infra docker image."),
    tag: str | None = typer.Option(None, help="Deepfellow Infra docker image tag (e.g. 0.15.0)"),
) -> None:
    """Update DeepFellow Infra."""
    check_infra_directory(directory)
    assert_docker()
    # Validate mutual exclusive image and tag
    if tag and image != DF_INFRA_IMAGE:
        raise typer.BadParameter("Only one if the `--tag` or `--image` options can be provided.")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    infra_values = read_env_file_to_dict(env_file)

    # Prepare the docker compose data
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file=compose_file)
    infra_service = compose["services"]["infra"]

    update_compose = False
    if local_image:
        if "pull_policy" not in infra_service:
            infra_service["pull_policy"] = "never"
            update_compose = True
    else:
        if "pull_policy" in infra_service:
            del infra_service["pull_policy"]
            update_compose = True

    if update_compose:
        save_compose_file(
            compose,
            directory / DOCKER_COMPOSE_CONFIG_FILENAME,
        )

    track_registry = bool(tag) or image == DF_INFRA_IMAGE
    current = str(infra_values["df_infra_image"])
    image = _resolve_image(image, tag, current)

    # Trust the running container, not .env alone: .env may point at an image that failed to pull
    # or was pulled but never started (restart declined).
    if (
        track_registry
        and not local_image
        and not image.endswith(":latest")
        and current == image
        and get_running_service_image("infra", directory) == image
    ):
        echo.success(f"DeepFellow Infra is already up to date ({image.rsplit(':', 1)[-1]}).")
        return

    # Pull before touching .env so a failed pull leaves .env pointing at the image that still runs.
    if not local_image:
        run(["docker", "pull", image], cwd=directory)

    if current != image:
        env_set(env_file, "INFRA_IMAGE", image, quiet=False, docker_note=False)

    echo.success("Deepfellow Infra updated.")
    if echo.confirm("Do you want to restart?", default=True):
        stop_infra(directory)
        start_infra(directory)
