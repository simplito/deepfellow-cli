# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Start infra typer command."""

from pathlib import Path

import typer

from deepfellow.common.config import read_env_file_to_dict
from deepfellow.common.defaults import DF_SERVER_IMAGE, DF_SERVER_IMAGE_HUB, DOCKER_COMPOSE_CONFIG_FILENAME
from deepfellow.common.docker import get_running_service_image, load_compose_file, save_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.env import env_set
from deepfellow.common.install import assert_docker
from deepfellow.common.registry import get_newest_image_tag
from deepfellow.common.system import run
from deepfellow.server.utils.docker import (
    has_nightshift_service,
    reconcile_nightshift_running_state,
    start_server,
    stop_server,
)
from deepfellow.server.utils.mongo_migration import is_legacy_mongo_install, migrate_mongo_to_app_user
from deepfellow.server.utils.nightshift_migration import (
    add_nightshift_to_install,
    resolve_nightshift_addition,
    warn_nightshift_declined,
)
from deepfellow.server.utils.options import directory_option
from deepfellow.server.utils.validation import check_server_directory

app = typer.Typer()


def _resolve_image(image: str, tag: str | None, current: str = "") -> str:
    """Return the final image reference to use for update."""
    if tag:
        return f"{DF_SERVER_IMAGE_HUB}:{tag}"
    if image == DF_SERVER_IMAGE:
        newest = get_newest_image_tag(DF_SERVER_IMAGE_HUB)
        if newest != current:
            echo.info(f"Newest image: {newest}")
        return newest
    return image


def _report_if_up_to_date(directory: Path, image: str, current: str, had_nightshift: bool) -> bool:
    """Return whether the server already runs `image` and has nothing else to update, telling the user so.

    Trusts the running container, not `.env` alone: `.env` may point at an image that failed to pull
    or was pulled but never started (restart declined). A legacy MongoDB install still needs the full
    update for its migration, even on the newest image.
    """
    up_to_date = (
        not image.endswith(":latest")
        and current == image
        and not is_legacy_mongo_install(directory)
        and get_running_service_image("server", directory) == image
    )
    if up_to_date:
        echo.success(f"DeepFellow Server is already up to date ({image.rsplit(':', 1)[-1]}).")
        if not had_nightshift:
            warn_nightshift_declined()
    return up_to_date


def _pull_and_pin_image(directory: Path, image: str, current: str, local_image: bool) -> None:
    """Pull `image` and point `.env` at it.

    Pulls before touching `.env`, so a failed pull leaves `.env` pointing at the image that still runs.
    """
    if not local_image:
        run(["docker", "pull", image], cwd=directory)

    if current != image:
        env_set(directory / ".env", "SERVER_IMAGE", image, quiet=False, docker_note=False)


def _sync_pull_policy(directory: Path, local_image: bool) -> None:
    """Set (`--local-image`) or remove `pull_policy: never` on `server` and, as it runs the same image, `nightshift`."""
    compose_file = directory / DOCKER_COMPOSE_CONFIG_FILENAME
    compose = load_compose_file(compose_file=compose_file)
    update_compose = False
    for name in ("server", "nightshift"):
        service = compose["services"].get(name)
        if service is None:
            continue
        if local_image and "pull_policy" not in service:
            service["pull_policy"] = "never"
            update_compose = True
        elif not local_image and "pull_policy" in service:
            del service["pull_policy"]
            update_compose = True

    if update_compose:
        save_compose_file(compose, compose_file)


@app.command()
def update(
    directory: Path = directory_option(exists=True),
    image: str = typer.Option(DF_SERVER_IMAGE, envvar="DF_SERVER_IMAGE", help="DeepFellow Server docker image."),
    local_image: bool = typer.Option(False, help="Use locally build DeepFellow Server docker image."),
    tag: str | None = typer.Option(None, help="Deepfellow Server docker image tag (e.g. 0.15.0)"),
    nightshift: bool | None = typer.Option(
        None,
        "--nightshift/--no-nightshift",
        help=(
            "On an install without the Nightshift worker: add it with RabbitMQ (the one in .env, otherwise a "
            "local one), or skip it, without asking."
        ),
    ),
    rabbitmq_url: str | None = typer.Option(
        None, help="host:port of an existing RabbitMQ to use when adding Nightshift (implies --nightshift)."
    ),
    rabbitmq_username: str = typer.Option(
        "", help="RabbitMQ username used when adding Nightshift (implies --nightshift)."
    ),
    rabbitmq_password: str = typer.Option(
        "", help="RabbitMQ password used when adding Nightshift (implies --nightshift)."
    ),
) -> None:
    """Update DeepFellow Server."""
    check_server_directory(directory)
    assert_docker()
    # Validate mutual exclusive image and tag
    if tag and image != DF_SERVER_IMAGE:
        raise typer.BadParameter("Only one if the `--tag` or `--image` options can be provided.")

    # Every question about adding Nightshift/RabbitMQ is asked here, before anything is written or
    # pulled, so declining or aborting leaves the install as it was.
    had_nightshift = has_nightshift_service(directory)
    nightshift_config = resolve_nightshift_addition(
        directory, nightshift, rabbitmq_url, rabbitmq_username, rabbitmq_password
    )

    # Prepare the starting point for .env
    env_file = directory / ".env"
    values = read_env_file_to_dict(env_file)

    _sync_pull_policy(directory, local_image)

    track_registry = bool(tag) or image == DF_SERVER_IMAGE
    current = str(values["df_server_image"])
    image = _resolve_image(image, tag, current)

    if (
        track_registry
        and not local_image
        and nightshift_config is None
        and _report_if_up_to_date(directory, image, current, had_nightshift)
    ):
        return

    _pull_and_pin_image(directory, image, current, local_image)

    if nightshift_config is not None:
        add_nightshift_to_install(directory, nightshift_config)

    # nightshift reuses the exact same image (DF_SERVER_IMAGE) - pull it too, so a subsequent
    # restart (below) picks up the new version for the worker as well, not just the server. An
    # install without Nightshift has no such service (compose fails on an unknown one), so it
    # only gets the server pulled. A local RabbitMQ added just now is pulled too, so a registry
    # problem shows up here, before the running server is stopped for the restart.
    has_nightshift = had_nightshift or nightshift_config is not None
    services = ["server"]
    if has_nightshift:
        services.append("nightshift")
    if nightshift_config is not None and nightshift_config.docker_compose:
        services.append("rabbitmq")
    run(["docker", "compose", "pull", *services], cwd=directory)
    # Installs from before the least-privilege MongoDB account still connect as MongoDB's root.
    # The root account is kept, so the running server works until the restart below switches it.
    mongo_migrated = is_legacy_mongo_install(directory) and migrate_mongo_to_app_user(directory)
    echo.success("DeepFellow Server updated.")
    if echo.confirm("Do you want to restart the server?", default=True):
        stop_server(directory)
        start_server(directory)
        # start_server()'s blanket `up` already recreates nightshift with the pulled image if it
        # should be up - this makes that schedule compliance an explicit, tested step rather than
        # an incidental side effect, matching `server restart`.
        reconcile_nightshift_running_state(directory)
    else:
        if nightshift_config is not None:
            added = "Nightshift and the local RabbitMQ were" if nightshift_config.docker_compose else "Nightshift was"
            echo.warning(f"{added} added but won't run until `deepfellow server start`.")
        if mongo_migrated:
            echo.warning(
                "DeepFellow Server keeps using MongoDB's root account until it is restarted "
                "(`deepfellow server restart`)."
            )

    if not has_nightshift:
        warn_nightshift_declined()
