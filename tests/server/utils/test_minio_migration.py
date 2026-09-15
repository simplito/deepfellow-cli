# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from deepfellow.common.defaults import SEAWEEDFS_S3_ACCESS_KEY, SEAWEEDFS_S3_SECRET_KEY
from deepfellow.common.docker import DockerError
from deepfellow.common.state import state
from deepfellow.server.utils.minio_migration import (
    _HEALTH_POLL_ATTEMPTS,
    MIGRATION_SKIPPED_LABEL,
    MIGRATION_SKIPPED_LABEL_CONFIRMED,
    _cleanup_migration_containers,
    _command_argv,
    _is_image_cached_locally,
    _mc_object_count,
    _migration_resource_names,
    _minio_credentials,
    _mirror_object_counts,
    _old_minio_mount_path,
    _remove_volume,
    _run_mc_mirror_with_retry,
    _wait_until_running,
    clear_migration_marker,
    ensure_legacy_minio_not_running,
    find_legacy_minio_service,
    migrate_minio_data_to_seaweedfs,
    should_keep_existing_minio,
)

_OLD_MINIO_SERVICE = {
    "container_name": "minio",
    "image": "minio/minio:RELEASE.2024-12-18T13-15-44Z",
    "environment": ["MINIO_ACCESS_KEY=minioadmin", "MINIO_SECRET_KEY=minioadmin"],
    "expose": ["9001", "9000"],
    "volumes": ["minio:/minio_data"],
    "command": 'minio server /minio_data --console-address ":9001"',
}

_VOLUME_NAME = "server_minio"
_NEW_VOLUME_NAME = "server_seaweedfs"
_SRC_CONTAINER, _DST_CONTAINER, _TMP_VOLUME = _migration_resource_names(_VOLUME_NAME)


def _resolve_volume_name_side_effect(directory: Path, volume_key: str) -> str | None:
    """A `resolve_compose_volume_name` stand-in that answers per volume key instead of one blanket value.

    The old `minio` volume and the new `seaweedfs` volume are resolved independently and must not
    collide, or the "does the target volume already exist" orphan check would misfire.
    """
    return {"minio": _VOLUME_NAME, "seaweedfs": _NEW_VOLUME_NAME}[volume_key]


def _volume_exists_side_effect(*, real: bool = True, tmp: bool = False, new: bool = False) -> Any:
    """A `volume_exists_or_raise` stand-in that answers per volume name instead of one blanket value.

    The old real volume, the migration's own temp staging volume, and the new target `seaweedfs`
    volume are checked independently, so a single `return_value=True` would wrongly trip one guard
    or another on every normal-path test.
    """

    def _side_effect(name: str) -> bool:
        if name == _TMP_VOLUME:
            return tmp
        if name == _NEW_VOLUME_NAME:
            return new
        return real

    return _side_effect


# --- find_legacy_minio_service -----------------------------------------------------------------


def test_find_legacy_minio_service_returns_none_when_no_compose_file(tmp_path: Path) -> None:
    assert find_legacy_minio_service(tmp_path) is None


def test_find_legacy_minio_service_returns_none_when_already_seaweedfs(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text('services:\n  minio:\n    image: "chrislusf/seaweedfs:3.97"\n')

    assert find_legacy_minio_service(tmp_path) is None


def test_find_legacy_minio_service_returns_service_when_old_minio_image(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        'services:\n  minio:\n    image: "minio/minio:RELEASE.2024-12-18T13-15-44Z"\n    command: "minio server"\n'
    )

    service = find_legacy_minio_service(tmp_path)

    assert service is not None
    assert service["image"] == "minio/minio:RELEASE.2024-12-18T13-15-44Z"


def test_find_legacy_minio_service_returns_none_when_compose_file_is_empty(tmp_path: Path) -> None:
    """An empty/truncated compose.yaml parses to `None` via `yaml.safe_load` - must not crash."""
    (tmp_path / "compose.yaml").write_text("")

    assert find_legacy_minio_service(tmp_path) is None


def test_find_legacy_minio_service_returns_none_when_migration_marker_present(tmp_path: Path) -> None:
    """A prior apply() migrated the data but failed before persisting compose.yaml - nothing left to decide."""
    (tmp_path / "compose.yaml").write_text(
        'services:\n  minio:\n    image: "minio/minio:RELEASE.2024-12-18T13-15-44Z"\n    command: "minio server"\n'
    )
    (tmp_path / ".seaweedfs_migration_complete").write_text("")

    assert find_legacy_minio_service(tmp_path) is None


def test_clear_migration_marker_removes_existing_marker(tmp_path: Path) -> None:
    marker = tmp_path / ".seaweedfs_migration_complete"
    marker.write_text("")

    clear_migration_marker(tmp_path)

    assert not marker.exists()


def test_clear_migration_marker_is_noop_when_no_marker_present(tmp_path: Path) -> None:
    clear_migration_marker(tmp_path)


@mock.patch("deepfellow.server.utils.minio_migration.echo")
def test_clear_migration_marker_logs_debug_on_failure(mock_echo: mock.MagicMock, tmp_path: Path) -> None:
    def fake_unlink(self: Path, *args: Any, **kwargs: Any) -> None:
        raise OSError("Permission denied")

    with mock.patch.object(Path, "unlink", autospec=True, side_effect=fake_unlink):
        clear_migration_marker(tmp_path)

    assert mock_echo.debug.call_count == 1


# --- ensure_legacy_minio_not_running -------------------------------------------------------------


@mock.patch("deepfellow.server.utils.minio_migration.is_service_running_or_raise")
def test_ensure_legacy_minio_not_running_skips_check_when_already_labeled(
    mock_is_running: mock.MagicMock, tmp_path: Path
) -> None:
    labeled_service = {**_OLD_MINIO_SERVICE, "labels": [MIGRATION_SKIPPED_LABEL]}

    ensure_legacy_minio_not_running(tmp_path, labeled_service)

    assert mock_is_running.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.is_service_running_or_raise", return_value=True)
def test_ensure_legacy_minio_not_running_raises_when_container_still_running(
    mock_is_running: mock.MagicMock, tmp_path: Path
) -> None:
    with pytest.raises(DockerError):
        ensure_legacy_minio_not_running(tmp_path, _OLD_MINIO_SERVICE)


@mock.patch("deepfellow.server.utils.minio_migration.is_service_running_or_raise", return_value=False)
def test_ensure_legacy_minio_not_running_passes_when_not_running(
    mock_is_running: mock.MagicMock, tmp_path: Path
) -> None:
    ensure_legacy_minio_not_running(tmp_path, _OLD_MINIO_SERVICE)


@mock.patch(
    "deepfellow.server.utils.minio_migration.is_service_running_or_raise",
    side_effect=DockerError("docker compose ps failed"),
)
def test_ensure_legacy_minio_not_running_raises_when_service_check_itself_fails(
    mock_is_running: mock.MagicMock, tmp_path: Path
) -> None:
    """A `docker compose ps` failure must not be silently treated as 'not running'."""
    with pytest.raises(DockerError):
        ensure_legacy_minio_not_running(tmp_path, _OLD_MINIO_SERVICE)


# --- should_keep_existing_minio -----------------------------------------------------------------


@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_returns_true_when_already_confirmed_and_image_still_cached(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
) -> None:
    labeled_service = {
        **_OLD_MINIO_SERVICE,
        "labels": [MIGRATION_SKIPPED_LABEL, MIGRATION_SKIPPED_LABEL_CONFIRMED],
    }

    assert should_keep_existing_minio(tmp_path, labeled_service) is True


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_reprompts_when_only_kept_via_non_interactive_default(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A container kept only via the `--non-interactive` safe default (no `_CONFIRMED` label) must
    not silently stay kept forever on a later *interactive* run - it must ask again."""
    labeled_service = {**_OLD_MINIO_SERVICE, "labels": [MIGRATION_SKIPPED_LABEL]}
    mock_echo.confirm.return_value = True

    assert should_keep_existing_minio(tmp_path, labeled_service) is False

    assert mock_echo.confirm.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_keeps_again_without_prompting_when_still_non_interactive(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """The non-interactive default is re-evaluated every time, but stays a silent no-op default
    for as long as the install stays non-interactive too."""
    labeled_service = {**_OLD_MINIO_SERVICE, "labels": [MIGRATION_SKIPPED_LABEL]}
    state.non_interactive = True
    try:
        assert should_keep_existing_minio(tmp_path, labeled_service) is True
    finally:
        state.non_interactive = False
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=False)
def test_should_keep_existing_minio_raises_when_labeled_but_image_gone_and_data_exists(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    labeled_service = {**_OLD_MINIO_SERVICE, "labels": [MIGRATION_SKIPPED_LABEL]}

    with pytest.raises(DockerError):
        should_keep_existing_minio(tmp_path, labeled_service)

    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", return_value=True)
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=False)
def test_should_keep_existing_minio_raises_when_image_gone_and_data_exists(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
) -> None:
    with pytest.raises(DockerError):
        should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE)


@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", return_value=False)
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=False)
def test_should_keep_existing_minio_migrates_silently_when_image_gone_but_no_data(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
) -> None:
    assert should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE) is False


@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise")
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value=None)
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_raises_when_volume_name_cannot_be_resolved(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A `docker compose config` failure must abort the destructive keep-or-migrate decision, not
    silently be treated as 'no data exists' - see the identical handling in
    `_resolve_migration_volumes()`."""
    with pytest.raises(DockerError, match="Could not resolve"):
        should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE)

    assert mock_volume_exists.call_count == 0


@mock.patch(
    "deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect(tmp=True)
)
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name", side_effect=_resolve_volume_name_side_effect
)
def test_should_keep_existing_minio_raises_when_orphaned_migration_volume_left_behind(
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A leftover staging volume from an interrupted prior migration attempt must abort the
    keep-or-migrate decision too, not just a fresh `migrate_minio_data_to_seaweedfs()` call - keeping
    MinIO in that state would point it at a real volume the interrupted attempt already wiped."""
    with pytest.raises(DockerError, match=_TMP_VOLUME):
        should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE)


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_migrates_without_prompting_when_yes_flag_set(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    state.yes = True
    try:
        assert should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE) is False
    finally:
        state.yes = False
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_keeps_without_prompting_when_non_interactive(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    state.non_interactive = True
    try:
        assert should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE) is True
    finally:
        state.non_interactive = False
    assert mock_echo.confirm.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_prompts_and_returns_keep_when_user_declines_migration(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_echo.confirm.return_value = False

    assert should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE) is True


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value="server_minio")
@mock.patch("deepfellow.server.utils.minio_migration._is_image_cached_locally", return_value=True)
def test_should_keep_existing_minio_prompts_and_returns_migrate_when_user_confirms(
    mock_image_cached: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_echo.confirm.return_value = True

    assert should_keep_existing_minio(tmp_path, _OLD_MINIO_SERVICE) is False


# --- small private helpers ----------------------------------------------------------------------


@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_is_image_cached_locally_true_when_docker_image_inspect_succeeds(mock_run: mock.MagicMock) -> None:
    mock_run.return_value = "[]"

    assert _is_image_cached_locally("minio/minio:RELEASE.2024-12-18T13-15-44Z") is True


@mock.patch("deepfellow.server.utils.minio_migration.run", side_effect=DockerError("no such image"))
def test_is_image_cached_locally_false_when_docker_image_inspect_fails(mock_run: mock.MagicMock) -> None:
    assert _is_image_cached_locally("minio/minio:RELEASE.2024-12-18T13-15-44Z") is False


def test_old_minio_mount_path_raises_when_no_minio_volume_entry_found() -> None:
    with pytest.raises(DockerError, match="Could not find"):
        _old_minio_mount_path({"volumes": ["minio-only-source"]})


def test_old_minio_mount_path_ignores_trailing_mount_mode() -> None:
    assert _old_minio_mount_path({"volumes": ["minio:/minio_data:ro"]}) == "/minio_data"


def test_old_minio_mount_path_ignores_unrelated_mount_ahead_of_the_data_volume() -> None:
    """A hand-added bind mount (e.g. TLS certs) ahead of the data volume must not be picked instead."""
    assert _old_minio_mount_path({"volumes": ["./certs:/certs", "minio:/minio_data"]}) == "/minio_data"


def test_minio_credentials_falls_back_to_default_when_no_environment() -> None:
    assert _minio_credentials({}) == ("minioadmin", "minioadmin")


def test_minio_credentials_reads_minio_root_user_and_password() -> None:
    service = {"environment": ["MINIO_ROOT_USER=custom-user", "MINIO_ROOT_PASSWORD=custom-pass"]}

    assert _minio_credentials(service) == ("custom-user", "custom-pass")


def test_minio_credentials_falls_back_to_access_and_secret_key() -> None:
    service = {"environment": ["MINIO_ACCESS_KEY=access-user", "MINIO_SECRET_KEY=secret-pass"]}

    assert _minio_credentials(service) == ("access-user", "secret-pass")


def test_minio_credentials_reads_mapping_form_environment() -> None:
    """Compose's `environment:` can be a mapping (`{KEY: VAL}`) instead of a `KEY=VAL` list."""
    service = {"environment": {"MINIO_ROOT_USER": "custom-user", "MINIO_ROOT_PASSWORD": "custom-pass"}}

    assert _minio_credentials(service) == ("custom-user", "custom-pass")


def test_command_argv_splits_string_form_command() -> None:
    assert _command_argv('minio server /minio_data --console-address ":9001"') == [
        "minio",
        "server",
        "/minio_data",
        "--console-address",
        ":9001",
    ]


def test_command_argv_passes_through_list_form_command() -> None:
    """Compose's `command:` can already be a YAML list (pre-split argv) instead of a single string."""
    assert _command_argv(["minio", "server", "/minio_data"]) == ["minio", "server", "/minio_data"]


@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run", return_value="false\n")
def test_wait_until_running_raises_after_exhausting_attempts(
    mock_run: mock.MagicMock, mock_sleep: mock.MagicMock
) -> None:
    with pytest.raises(DockerError, match="never started"):
        _wait_until_running("minio-migrate-src")


@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_wait_until_running_retries_until_running(mock_run: mock.MagicMock, mock_sleep: mock.MagicMock) -> None:
    mock_run.side_effect = ["false\n", "true\n"]

    _wait_until_running("minio-migrate-src")

    assert mock_run.call_count == 2
    assert mock_sleep.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_wait_until_running_retries_past_a_transient_inspect_failure(
    mock_run: mock.MagicMock, mock_sleep: mock.MagicMock
) -> None:
    """A single `docker inspect` hiccup must not abort the whole wait immediately."""
    mock_run.side_effect = [DockerError("daemon hiccup"), "true\n"]

    _wait_until_running("minio-migrate-src")

    assert mock_run.call_count == 2
    assert mock_sleep.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run", side_effect=DockerError("connection refused"))
def test_run_mc_mirror_with_retry_raises_last_error_after_exhausting_attempts(
    mock_run: mock.MagicMock, mock_sleep: mock.MagicMock
) -> None:
    with pytest.raises(DockerError, match="connection refused"):
        _run_mc_mirror_with_retry("df-network", "minioadmin", "minioadmin", "src-container", "dst-container")

    assert mock_run.call_count == _HEALTH_POLL_ATTEMPTS


@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_run_mc_mirror_with_retry_succeeds_once_ready(mock_run: mock.MagicMock, mock_sleep: mock.MagicMock) -> None:
    mock_run.side_effect = [DockerError("connection refused"), "mirrored\n"]

    _run_mc_mirror_with_retry("df-network", "minioadmin", "minioadmin", "src-container", "dst-container")

    assert mock_run.call_count == 2
    assert mock_sleep.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_run_mc_mirror_with_retry_quotes_credentials_with_shell_metacharacters(mock_run: mock.MagicMock) -> None:
    """A password containing shell metacharacters must not break out of the `sh -c` script."""
    _run_mc_mirror_with_retry(
        "df-network", "user`whoami`", "pass$(rm -rf /) with spaces", "src-container", "dst-container"
    )

    script = mock_run.call_args[0][0][-1]
    assert "'user`whoami`'" in script
    assert "'pass$(rm -rf /) with spaces'" in script


@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_run_mc_mirror_with_retry_always_authenticates_dst_with_seaweedfs_defaults(
    mock_run: mock.MagicMock,
) -> None:
    """The destination is a fresh SeaweedFS container whose identity file only ever recognizes the
    fixed `SEAWEEDFS_S3_ACCESS_KEY`/`SEAWEEDFS_S3_SECRET_KEY` - using the old MinIO's own,
    potentially different, credentials for the `dst` alias too would make every migration off a
    non-default MinIO install fail."""
    _run_mc_mirror_with_retry("df-network", "real-minio-user", "real-minio-password", "src-container", "dst-container")

    script = mock_run.call_args[0][0][-1]
    assert "mc alias set src http://src-container:9000 real-minio-user real-minio-password" in script
    assert f"mc alias set dst http://dst-container:9000 {SEAWEEDFS_S3_ACCESS_KEY} {SEAWEEDFS_S3_SECRET_KEY}" in script


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.run", side_effect=DockerError("boom"))
def test_cleanup_migration_containers_swallows_every_failure(
    mock_run: mock.MagicMock, mock_echo: mock.MagicMock
) -> None:
    _cleanup_migration_containers("src-container", "dst-container")

    assert mock_run.call_count == 4  # 2 containers x (stop, rm)
    assert mock_echo.debug.call_count == 2  # the "stop" failures, non-critical (rm still follows)
    assert mock_echo.warning.call_count == 2  # the "rm" failures, surfaced like _remove_volume's


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.run", side_effect=DockerError("boom"))
def test_remove_volume_warns_on_failure(mock_run: mock.MagicMock, mock_echo: mock.MagicMock) -> None:
    _remove_volume("tmp-volume")

    assert mock_run.call_count == 1
    assert mock_echo.warning.call_count == 1


@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_mc_object_count_sums_multiple_bucket_lines(mock_run: mock.MagicMock) -> None:
    """`mc du --json <alias>` prints one JSON line per bucket, not a single summary line."""
    mock_run.return_value = '{"objects": 5}\n{"objects": 7}\n'

    assert _mc_object_count("df-network", "src", "minioadmin", "minioadmin", "src-container") == 12


@mock.patch("deepfellow.server.utils.minio_migration.run", return_value="")
def test_mc_object_count_is_zero_for_a_bucket_less_install(mock_run: mock.MagicMock) -> None:
    """A fresh/empty MinIO install has zero buckets - zero `mc du` lines must count as 0, not an error."""
    assert _mc_object_count("df-network", "src", "minioadmin", "minioadmin", "src-container") == 0


@mock.patch("deepfellow.server.utils.minio_migration.run", return_value="not json\n")
def test_mc_object_count_raises_on_unparseable_output(mock_run: mock.MagicMock) -> None:
    with pytest.raises(DockerError, match="Could not parse"):
        _mc_object_count("df-network", "src", "minioadmin", "minioadmin", "src-container")


@mock.patch("deepfellow.server.utils.minio_migration.run")
def test_mirror_object_counts_queries_each_side_separately_with_its_own_credentials(
    mock_run: mock.MagicMock,
) -> None:
    """The two sides can have any, independent number of buckets (including zero), so each is
    queried with its own `mc du` invocation rather than one shared, line-count-sensitive call - and
    the destination always authenticates with the fixed SeaweedFS defaults, never the source's real
    (potentially different) credentials. See `_mc_object_count()` and `_run_mc_mirror_with_retry()`.
    """
    mock_run.side_effect = ['{"objects": 3}\n{"objects": 2}\n', '{"objects": 5}\n']

    counts = _mirror_object_counts(
        "df-network", "real-minio-user", "real-minio-password", "src-container", "dst-container"
    )

    assert counts == (5, 5)
    src_script = mock_run.call_args_list[0].args[0][-1]
    dst_script = mock_run.call_args_list[1].args[0][-1]
    assert "mc alias set src http://src-container:9000 real-minio-user real-minio-password" in src_script
    assert (
        f"mc alias set dst http://dst-container:9000 {SEAWEEDFS_S3_ACCESS_KEY} {SEAWEEDFS_S3_SECRET_KEY}" in dst_script
    )


def test_migration_resource_names_derived_from_volume_name() -> None:
    assert _migration_resource_names("server_minio") == (
        "server_minio-migrate-src",
        "server_minio-migrate-dst",
        "server_minio-migrate-tmp",
    )


# --- migrate_minio_data_to_seaweedfs ------------------------------------------------------------


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=None)
def test_migrate_is_noop_when_no_legacy_minio_service_found(
    mock_find_legacy: mock.MagicMock, mock_run: mock.MagicMock, tmp_path: Path
) -> None:
    """Guards against a stale, replayed keep/migrate decision re-running against already-migrated data."""
    migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", return_value=False)
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value=_VOLUME_NAME)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_is_noop_when_volume_resolved_but_genuinely_absent(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise")
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value=None)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_volume_name_cannot_be_resolved(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    with pytest.raises(DockerError, match="Could not resolve"):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0
    assert mock_volume_exists.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=lambda directory, volume_key: None if volume_key == "seaweedfs" else _VOLUME_NAME,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_target_volume_name_cannot_be_resolved(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    with pytest.raises(DockerError, match="Could not resolve the target"):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch(
    "deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect(tmp=True)
)
@mock.patch("deepfellow.server.utils.minio_migration.resolve_compose_volume_name", return_value=_VOLUME_NAME)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_leftover_temp_volume_from_interrupted_attempt_exists(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A leftover staging volume from an interrupted prior attempt must never be silently reused."""
    with pytest.raises(DockerError, match=_TMP_VOLUME):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_target_seaweedfs_volume_already_exists(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A leftover `seaweedfs` volume from an interrupted prior attempt must never be silently reused."""
    with (
        mock.patch(
            "deepfellow.server.utils.minio_migration.volume_exists_or_raise",
            side_effect=_volume_exists_side_effect(new=True),
        ),
        pytest.raises(DockerError, match=_NEW_VOLUME_NAME),
    ):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_seaweedfs_s3_config_write_fails(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "seaweedfs_s3_config.json"

    def fake_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == config_path:
            raise OSError("Permission denied")
        return len(args[0]) if args else 0

    with (
        mock.patch.object(Path, "write_text", autospec=True, side_effect=fake_write_text),
        pytest.raises(DockerError, match="Permission denied"),
    ):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert mock_run.call_count == 0


def _fake_run_factory(src_objects: int = 3, dst_objects: int | None = None) -> Any:
    """A `run()` stand-in that answers health-poll inspects as immediately healthy/running, and the
    post-mirror `mc du` verification with a matching object count on both sides by default.
    """
    if dst_objects is None:
        dst_objects = src_objects

    def fake_run(command: Sequence[str], **_kwargs: Any) -> str | None:
        if command[:2] == ["docker", "inspect"]:
            return "true\n"
        joined = " ".join(str(part) for part in command)
        if "mc du --json src" in joined:
            return f'{{"objects": {src_objects}}}\n'
        if "mc du --json dst" in joined:
            return f'{{"objects": {dst_objects}}}\n'
        return None

    return fake_run


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_runs_full_pipeline_and_cleans_up_on_success(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    mock_run.side_effect = _fake_run_factory()

    migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["docker", "volume", "create", _TMP_VOLUME] in commands
    assert ["docker", "volume", "create", _NEW_VOLUME_NAME] in commands
    assert any(cmd[:3] == ["docker", "run", "--rm"] and "alpine" in cmd and "cp" in cmd for cmd in commands)
    # The old MinIO volume is only ever read, never wiped.
    assert not any(cmd[:3] == ["docker", "run", "--rm"] and "find" in cmd and "-delete" in cmd for cmd in commands)
    src_run = next(cmd for cmd in commands if cmd[:3] == ["docker", "run", "-d"] and _SRC_CONTAINER in cmd)
    assert "MINIO_ROOT_USER=minioadmin" in src_run
    assert "MINIO_ROOT_PASSWORD=minioadmin" in src_run
    assert "MINIO_ACCESS_KEY=minioadmin" in src_run
    assert "MINIO_SECRET_KEY=minioadmin" in src_run
    dst_run = next(cmd for cmd in commands if cmd[:3] == ["docker", "run", "-d"] and _DST_CONTAINER in cmd)
    assert f"{_NEW_VOLUME_NAME}:/data" in dst_run
    assert "--hostname" in dst_run
    assert dst_run[dst_run.index("--hostname") + 1] == "seaweedfs"
    assert any("mc mirror --overwrite src/ dst/" in " ".join(cmd) for cmd in commands)
    # Cleanup on success: stop+rm both containers, remove the staging volume, and finally drop the
    # now-superseded legacy MinIO volume.
    assert ["docker", "stop", "-t", "30", _SRC_CONTAINER] in commands
    assert ["docker", "stop", "-t", "30", _DST_CONTAINER] in commands
    assert ["docker", "rm", "-f", _SRC_CONTAINER] in commands
    assert ["docker", "rm", "-f", _DST_CONTAINER] in commands
    assert ["docker", "volume", "rm", _TMP_VOLUME] in commands
    assert ["docker", "volume", "rm", _VOLUME_NAME] in commands
    assert (tmp_path / "seaweedfs_s3_config.json").exists()
    assert (tmp_path / ".seaweedfs_migration_complete").exists()


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_when_marker_file_write_fails_after_successful_mirror(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A failed marker write must not look like a successful, complete migration."""
    mock_run.side_effect = _fake_run_factory()
    marker_path = tmp_path / ".seaweedfs_migration_complete"

    def fake_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        if self == marker_path:
            raise OSError("Permission denied")
        return len(args[0]) if args else 0

    with (
        mock.patch.object(Path, "write_text", autospec=True, side_effect=fake_write_text),
        pytest.raises(DockerError, match="failed to record it"),
    ):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_cleans_up_but_leaves_original_minio_volume_untouched_when_mc_mirror_fails(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """On failure, the disposable staging/target volumes are cleaned up, but the original MinIO volume - never
    wiped in the first place - is left exactly as it is, and the error says so."""
    fake_run = _fake_run_factory()

    def failing_run(command: Sequence[str], **kwargs: Any) -> str | None:
        if any("mc mirror" in str(part) for part in command):
            raise DockerError("mc mirror failed")
        return fake_run(command, **kwargs)

    mock_run.side_effect = failing_run

    with pytest.raises(DockerError, match="untouched") as exc_info:
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert _VOLUME_NAME in str(exc_info.value)
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["docker", "rm", "-f", _SRC_CONTAINER] in commands
    assert ["docker", "rm", "-f", _DST_CONTAINER] in commands
    assert ["docker", "volume", "rm", _TMP_VOLUME] in commands
    assert ["docker", "volume", "rm", _NEW_VOLUME_NAME] in commands
    assert ["docker", "volume", "rm", _VOLUME_NAME] not in commands


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_raises_and_leaves_minio_volume_when_object_counts_dont_match(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A successful-looking `mc mirror` that actually moved nothing must not be trusted or drop the original."""
    mock_run.side_effect = _fake_run_factory(src_objects=5, dst_objects=0)

    with pytest.raises(DockerError, match=_VOLUME_NAME):
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["docker", "volume", "rm", _VOLUME_NAME] not in commands
    assert not (tmp_path / ".seaweedfs_migration_complete").exists()


@mock.patch("deepfellow.server.utils.minio_migration.echo")
@mock.patch("deepfellow.server.utils.minio_migration.time.sleep")
@mock.patch("deepfellow.server.utils.minio_migration.run")
@mock.patch("deepfellow.server.utils.minio_migration.volume_exists_or_raise", side_effect=_volume_exists_side_effect())
@mock.patch(
    "deepfellow.server.utils.minio_migration.resolve_compose_volume_name",
    side_effect=_resolve_volume_name_side_effect,
)
@mock.patch("deepfellow.server.utils.minio_migration.find_legacy_minio_service", return_value=_OLD_MINIO_SERVICE)
def test_migrate_removes_staging_volume_and_reports_untouched_data_when_copy_fails(
    mock_find_legacy: mock.MagicMock,
    mock_resolve_volume: mock.MagicMock,
    mock_volume_exists: mock.MagicMock,
    mock_run: mock.MagicMock,
    mock_sleep: mock.MagicMock,
    mock_echo: mock.MagicMock,
    tmp_path: Path,
) -> None:
    """A failure while copying to the staging volume must not touch the original MinIO volume, and must not
    leave an orphaned staging volume blocking every future run."""
    fake_run = _fake_run_factory()

    def failing_run(command: Sequence[str], **kwargs: Any) -> str | None:
        if command[:3] == ["docker", "run", "--rm"] and "cp" in command:
            raise DockerError("no space left on device")
        return fake_run(command, **kwargs)

    mock_run.side_effect = failing_run

    with pytest.raises(DockerError, match="untouched") as exc_info:
        migrate_minio_data_to_seaweedfs(tmp_path, "df-network", _OLD_MINIO_SERVICE)

    assert _VOLUME_NAME in str(exc_info.value)
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["docker", "volume", "rm", _TMP_VOLUME] in commands
    assert ["docker", "volume", "create", _NEW_VOLUME_NAME] not in commands
    assert not (tmp_path / ".seaweedfs_migration_complete").exists()
