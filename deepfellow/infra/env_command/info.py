# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""infra info command."""

from pathlib import Path

import typer

from deepfellow.common.echo import echo
from deepfellow.common.env import get_envs_list
from deepfellow.infra.utils.options import directory_option

app = typer.Typer()


@app.command()
def info(
    directory: Path = directory_option(),
) -> None:
    """Display environment configuration."""
    env_file = directory / ".env"
    envs = get_envs_list(env_file)
    extended_envs = []
    for env in envs:
        extended_envs.append(env)
        if env.startswith("DF_INFRA_URL"):
            extended_envs.append(env.replace("INFRA_URL", "INFRA_MESH_URL").replace("http", "ws"))

    display = "\n".join(extended_envs)
    echo.info(f"Variables stored in {env_file}\n{display}")
