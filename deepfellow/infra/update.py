# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start infra typer command."""

from pathlib import Path
from typing import Annotated

import typer

from deepfellow.common.config import (
    read_env_file_to_dict,
)
from deepfellow.common.defaults import (
    DF_INFRA_IMAGE_HUB,
    DOCKER_COMPOSE_CONFIG_FILENAME,
    INFRA_BIND_ADDRESS,
)
from deepfellow.common.docker import (
    bind_port_mappings,
    get_running_service_image,
    load_compose_file,
    refresh_ca_trust_bundle,
    save_compose_file,
)
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.registry import (
    assert_cli_compatible,
    assert_not_downgrade,
    get_newest_image_tag,
    require_local_image_tag,
    warn_version_check_skipped,
)
from deepfellow.common.system import run
from deepfellow.infra.utils.docker import start_infra, stop_infra
from deepfellow.infra.utils.options import directory_option
from deepfellow.infra.utils.validation import check_infra_directory

app = typer.Typer()


def _resolve_image(
    image: str | None, tag: str | None, current: str = "", local_image: bool = False, skip_version_check: bool = False
) -> str:
    """Return the final image reference to use for update, exiting if this CLI can't install it.

    A locally built image is taken as it is: it needs neither the registry nor the checks, only an explicit tag.
    Without an image or tag the newest release this CLI supports is used.
    """
    if tag:
        image = f"{DF_INFRA_IMAGE_HUB}:{tag}"
    if local_image:
        return require_local_image_tag(image, "Infra", image_hint="`--image <name>:<tag>` or `--tag <tag>`")
    if skip_version_check:
        warn_version_check_skipped()
    if image is None:
        newest = get_newest_image_tag(DF_INFRA_IMAGE_HUB)
        if not skip_version_check:
            assert_not_downgrade("Infra", current, newest)
        if newest != current:
            echo.info(f"Newest image: {newest}")
        return newest
    if not skip_version_check:
        assert_cli_compatible("Infra", image)
    return image


@app.command()
def update(
    directory: Path = directory_option(exists=True),
    image: str | None = typer.Option(
        None,
        envvar="DF_INFRA_IMAGE",
        help="DeepFellow Infra docker image with a version tag. Default: the newest release compatible with this CLI.",
    ),
    local_image: bool = typer.Option(
        False, help="Use locally build DeepFellow Infra docker image. Requires --tag or an explicit tag in --image."
    ),
    tag: str | None = typer.Option(None, help="Deepfellow Infra docker image tag (e.g. 0.15.0)"),
    skip_version_check: Annotated[
        bool,
        typer.Option(
            "--skip-version-check",
            help="Skip the CLI/Infra version compatibility and downgrade checks (for development).",
        ),
    ] = False,
) -> None:
    """Update DeepFellow Infra."""
    check_infra_directory(directory)
    assert_docker()
    # Validate mutual exclusive image and tag
    if tag and image is not None:
        raise typer.BadParameter("Only one if the `--tag` or `--image` options can be provided.")

    # Prepare the starting point for .env
    env_file = directory / ".env"
    infra_values = read_env_file_to_dict(env_file)

    # Resolved and validated before anything is rewritten, so a refused image leaves the install untouched.
    track_registry = image is None and not tag
    current = str(infra_values["df_infra_image"])
    image = _resolve_image(image, tag, current, local_image, skip_version_check)

    # Prepare the docker compose data
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file=compose_file)
    infra_service = compose["services"]["infra"]

    # An install from before bind addresses publishes infra's port with no host part. Adding
    # DF_INFRA_BIND_ADDRESS keeps it on all interfaces (the variable is unset) but lets it take effect.
    update_compose = bind_port_mappings(infra_service, INFRA_BIND_ADDRESS)
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

    # Also when the image is up to date: the bundle's public CAs come from this CLI, and the CA may have changed
    refresh_ca_trust_bundle(directory, infra_service)

    # Trust the running container, not .env alone: .env may point at an image that failed to pull
    # or was pulled but never started (restart declined).
    if (
        track_registry
        and not local_image
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
