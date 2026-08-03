# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from unittest import mock

from deepfellow.infra.utils.docker import start_infra, stop_infra


@mock.patch("deepfellow.infra.utils.docker.run")
@mock.patch("deepfellow.infra.utils.docker.ensure_network")
@mock.patch("deepfellow.infra.utils.docker.get_docker_network")
def test_start_infra_ensures_network_and_starts_compose(
    mock_get_docker_network: mock.MagicMock,
    mock_ensure_network: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
):
    mock_get_docker_network.return_value = "df_network"

    start_infra(tmp_path)

    assert mock_get_docker_network.call_count == 1
    assert mock_get_docker_network.call_args == mock.call(tmp_path)
    assert mock_ensure_network.call_count == 1
    assert mock_ensure_network.call_args == mock.call("df_network")
    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(
        ["docker", "compose", "up", "-d", "--wait", "--remove-orphans"], cwd=tmp_path
    )


@mock.patch("deepfellow.infra.utils.docker.run")
def test_stop_infra_stops_compose_service(mock_run: mock.MagicMock, tmp_path: Path):
    stop_infra(tmp_path)

    assert mock_run.call_count == 1
    assert mock_run.call_args == mock.call(["docker", "compose", "stop", "infra"], cwd=tmp_path)
