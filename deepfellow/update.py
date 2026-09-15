# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Top-level update command for all DeepFellow components."""

from collections.abc import Callable
from pathlib import Path

import typer

from deepfellow.cli.update import update as update_cli
from deepfellow.common.defaults import (
    DF_INFRA_DIRECTORY,
    DF_INFRA_IMAGE,
    DF_SERVER_IMAGE,
    DOCKER_COMPOSE_CONFIG_FILENAME,
)
from deepfellow.common.docker import load_compose_file
from deepfellow.common.echo import echo
from deepfellow.common.exceptions import InstallError, translate_to_install_error
from deepfellow.infra.update import update as update_infra
from deepfellow.server.update import update as update_server
from deepfellow.server.utils.options import get_default_server_directory

app = typer.Typer()


def _uses_local_image(directory: Path, service: str) -> bool:
    """Return whether `service` in `directory`'s compose file is pinned to a local image.

    A `pull_policy: never` on the service means the user deliberately installed it with
    `--local-image`, pointing it at an image only they built. `update`'s own `local_image=False`
    would otherwise strip that pin and overwrite it with the registry image.
    """
    compose = load_compose_file(directory / DOCKER_COMPOSE_CONFIG_FILENAME)
    return compose.get("services", {}).get(service, {}).get("pull_policy") == "never"


def _run_step(step: Callable[[], None]) -> bool:
    """Run one update step, swallowing the InstallError it raises on failure.

    The underlying command has already reported the specific error via echo before raising;
    `translate_to_install_error` catches it (and any other typer/Docker/OSError failure, even
    in `--debug` mode) so a single failing component (e.g. Docker not running for Infra) can't
    abort the rest of `update`. Returns whether the step succeeded.
    """
    try:
        translate_to_install_error(step)()
    except InstallError as exc:
        echo.error(str(exc))
        return False
    return True


@app.command()
def update() -> None:
    """Update DeepFellow CLI, Infra, and Server.

    The CLI is always updated. Infra and Server are updated only if installed locally
    (their directory exists); a missing component is skipped rather than treated as an
    error. A component pinned to a locally built image (`pull_policy: never`, set by its
    own `--local-image` install/update) is also skipped, rather than overwritten with the
    registry image. If any attempted step fails, `update` exits with a non-zero status
    after still attempting the remaining steps.
    """
    ok = _run_step(update_cli)

    if DF_INFRA_DIRECTORY.is_dir():
        if _uses_local_image(DF_INFRA_DIRECTORY, "infra"):
            echo.info("DeepFellow Infra uses a locally built image, skipping.")
        else:
            ok = (
                _run_step(
                    lambda: update_infra(
                        directory=DF_INFRA_DIRECTORY, image=DF_INFRA_IMAGE, local_image=False, tag=None
                    )
                )
                and ok
            )
    else:
        echo.info("DeepFellow Infra not installed, skipping.")

    server_directory = get_default_server_directory()
    if server_directory.is_dir():
        if _uses_local_image(server_directory, "server"):
            echo.info("DeepFellow Server uses a locally built image, skipping.")
        else:
            ok = (
                _run_step(
                    lambda: update_server(
                        directory=server_directory, image=DF_SERVER_IMAGE, local_image=False, tag=None
                    )
                )
                and ok
            )
    else:
        echo.info("DeepFellow Server not installed, skipping.")

    if not ok:
        raise typer.Exit(1)
