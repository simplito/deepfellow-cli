# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Migrate a legacy MinIO-backed Milvus install to the SeaweedFS S3 gateway.

MinIO's Docker Hub image tags were removed upstream, so `DOCKER_COMPOSE_MILVUS`'s `seaweedfs` service
now points at SeaweedFS's S3 gateway instead of MinIO. SeaweedFS does not understand MinIO's on-disk
format, so an existing install's Milvus data (stored via the old MinIO container's `minio` volume)
needs to move across through the S3 API on both sides into a fresh `seaweedfs` volume, with the old
`minio` volume removed only once that's verified to have succeeded.
"""

import json
import shlex
import time
from pathlib import Path
from typing import Any

from deepfellow.common.defaults import (
    DOCKER_COMPOSE_MILVUS,
    SEAWEEDFS_S3_ACCESS_KEY,
    SEAWEEDFS_S3_CONFIG,
    SEAWEEDFS_S3_SECRET_KEY,
)
from deepfellow.common.docker import (
    DockerError,
    is_service_running_or_raise,
    load_compose_file,
    resolve_compose_volume_name,
    volume_exists_or_raise,
)
from deepfellow.common.echo import echo
from deepfellow.common.state import state
from deepfellow.common.system import run

MIGRATION_SKIPPED_LABEL = "deepfellow.migration-skipped=minio-seaweedfs"

# Written alongside `MIGRATION_SKIPPED_LABEL` only when the keep-instead-of-migrate decision was a
# genuine, deliberate choice (an interactive confirm, or carrying forward an already-confirmed
# decision) - never for the `--non-interactive` safe default. `MIGRATION_SKIPPED_LABEL` alone means
# "this MinIO container is intentionally being kept running, don't treat that as blocking a
# reinstall"; this second label additionally means "and don't ask again either." Without the
# distinction, a single unattended `--non-interactive` install would permanently silence the
# migration prompt for every future *interactive* install too, even though nobody ever actually
# chose to keep MinIO forever - see `should_keep_existing_minio()`.
MIGRATION_SKIPPED_LABEL_CONFIRMED = "deepfellow.migration-skip-confirmed=minio-seaweedfs"

# Written the moment `mc mirror` verifiably succeeds - before any of apply()'s later, unrelated
# fallible steps (init-mongo.sh write, directory mkdir()s, the final save_compose_file()) get a
# chance to fail. compose.yaml itself isn't updated until apply() finishes building and writes the
# whole thing, so without this marker a retry after one of those later failures would still find
# the old MinIO image in compose.yaml and re-run the full copy/wipe/mirror sequence against data
# that's already in SeaweedFS's format.
_MIGRATION_MARKER_FILENAME = ".seaweedfs_migration_complete"

_MC_IMAGE = "quay.io/minio/mc:RELEASE.2025-08-13T08-35-41Z"
_HEALTH_POLL_ATTEMPTS = 30
_HEALTH_POLL_INTERVAL_SECONDS = 2
_STOP_TIMEOUT_SECONDS = 30


def _migration_marker_path(directory: Path) -> Path:
    return directory / _MIGRATION_MARKER_FILENAME


def clear_migration_marker(directory: Path) -> None:
    """Remove the migration-complete marker once compose.yaml itself has been persisted.

    Best-effort and safe to call unconditionally (including when no migration ever ran): the
    marker's only job is to survive a failure between a successful migration and apply() finishing
    - once compose.yaml is written, `find_legacy_minio_service()` no longer finds the old image
    there either, so the marker is redundant from that point on. Failing to remove it changes
    nothing functionally, only leaves a harmless leftover file.
    """
    try:
        _migration_marker_path(directory).unlink(missing_ok=True)
    except OSError as exc:
        echo.debug(f"Failed to remove migration marker: {exc}")


def find_legacy_minio_service(directory: Path) -> dict[str, Any] | None:
    """Return the previous compose.yaml's `minio` service if it's still the old MinIO image.

    Returns `None` for a brand-new install (no compose.yaml yet), an already-migrated or
    already-fresh SeaweedFS install (nothing to do), or any install without a `minio` service at
    all (qdrant, or a custom vector DB server). Also `None` once `_migration_marker_path()` exists,
    even if compose.yaml still names the old image - that means a previous `apply()` finished
    migrating the data but failed before it could persist compose.yaml, so there's no keep/migrate
    decision left to make; only that stale compose.yaml write is still pending.
    """
    if _migration_marker_path(directory).exists():
        return None

    previous_compose = load_compose_file(directory / "compose.yaml")
    if not isinstance(previous_compose, dict):
        return None

    minio_service = previous_compose.get("services", {}).get("minio")
    if not isinstance(minio_service, dict) or not str(minio_service.get("image", "")).startswith("minio/minio"):
        return None

    return minio_service


def _is_migration_skip_marked(old_service: dict[str, Any]) -> bool:
    """Whether a previous apply() run kept MinIO running instead of migrating, for any reason."""
    return MIGRATION_SKIPPED_LABEL in (old_service.get("labels") or [])


def _is_migration_skip_confirmed(old_service: dict[str, Any]) -> bool:
    """Whether keeping MinIO was a deliberate, remembered decision - see `MIGRATION_SKIPPED_LABEL_CONFIRMED`."""
    return MIGRATION_SKIPPED_LABEL_CONFIRMED in (old_service.get("labels") or [])


def _is_image_cached_locally(image: str) -> bool:
    """Whether `image` is already present in the local Docker image cache."""
    try:
        run(["docker", "image", "inspect", image], capture_output=True, raises=DockerError)
    except DockerError:
        return False

    return True


def ensure_legacy_minio_not_running(directory: Path, old_service: dict[str, Any], *, force: bool = False) -> None:
    """Abort (`DockerError`) if the previous install's MinIO container is still running.

    Migrating requires copying the container's data volume, which must not happen while something
    is actively writing to it. Separate from `should_keep_existing_minio()` so a caller can run
    this check as early as possible - before any other install prompt - instead of only once
    `should_keep_existing_minio()` is reached partway through configuration. Not checked (unless
    `force=True`) when `MIGRATION_SKIPPED_LABEL` is present: a kept container is expected to still be
    running, and only the migration path touches its volume.

    That skip is only a heuristic proxy for "this run will probably keep it running again" - it is
    NOT a guarantee, since only `MIGRATION_SKIPPED_LABEL_CONFIRMED` pins the decision forever (see
    `should_keep_existing_minio()`); a base-label-only container can still end up migrated this run,
    e.g. via `--yes` or an interactive re-prompt. Callers that already know for certain the container
    is about to be migrated - i.e. right before the destructive volume copy, once
    `should_keep_existing_minio()` has actually returned `False` - must pass `force=True` so a stale
    label can never let a live copy proceed unchecked.
    """
    if not force and _is_migration_skip_marked(old_service):
        return

    if is_service_running_or_raise("minio", directory):
        echo.error(
            "The existing MinIO container is still running. Run `deepfellow server stop` before "
            "installing again, so its data volume isn't touched while a container is actively "
            "writing to it."
        )
        raise DockerError("MinIO container is running")


def should_keep_existing_minio(directory: Path, old_service: dict[str, Any]) -> bool:
    """Decide whether to keep the existing MinIO container instead of migrating to SeaweedFS.

    Returns `True` to keep MinIO as-is, `False` to migrate its data to SeaweedFS. Aborts the
    installation entirely (`typer.Exit`, via `DockerError`) if the old image is gone from both
    Docker Hub and the local cache while real data still exists - neither keeping nor migrating is
    possible then, and silently falling through to a fresh SeaweedFS install would abandon that
    data without saying so.

    Call `ensure_legacy_minio_not_running()` before this - it is not repeated here so the running
    check can run earlier, before other install prompts. Also aborts (`DockerError`, via
    `ensure_no_orphaned_migration_volume()`) if a previous migration attempt left its temp volume
    behind - keeping MinIO in that state would point it at a real volume already wiped by that
    attempt, silently orphaning the temp volume that holds the only surviving copy of the data.

    Only a *confirmed* previous decision (`MIGRATION_SKIPPED_LABEL_CONFIRMED` - an explicit
    interactive choice, or one already carried forward) is honored silently forever. A container
    kept only via the `--non-interactive` safe default (`MIGRATION_SKIPPED_LABEL` alone) is kept for
    this run too, but the decision is re-evaluated - and, outside `--non-interactive`, re-prompted -
    every time, so one unattended install can't permanently silence the migration prompt for every
    later interactive install.
    """
    ensure_no_orphaned_migration_volume(directory)

    image = str(old_service.get("image", ""))
    image_cached = _is_image_cached_locally(image)
    volume_name = resolve_compose_volume_name(directory, "minio")
    if volume_name is None:
        raise DockerError(
            "Could not resolve the existing MinIO data volume's name (`docker compose config` "
            "failed). Aborting rather than deciding a destructive keep-or-migrate choice without "
            "knowing whether real data exists."
        )
    # `volume_exists_or_raise()`, not `volume_exists()`: this decides whether it's safe to report
    # "no existing data" at a destructive fork (keep vs. migrate) - a transient inspect failure
    # must not be silently treated as confirmed absence here.
    has_data = volume_exists_or_raise(volume_name)

    if _is_migration_skip_marked(old_service):
        if image_cached and _is_migration_skip_confirmed(old_service):
            return True
        if not image_cached:
            # A previously-kept image has since vanished from the local cache (e.g. `docker image
            # prune`) - keeping it would write a `pull_policy: never` service compose can never
            # start. Fall through to the same not-cached handling a first-time decision would get,
            # instead of blindly honoring a label recorded when the image was still available.
            echo.warning(
                f"The existing MinIO container was previously kept as-is, but its image ('{image}') "
                "is no longer cached locally and can no longer be pulled - re-evaluating whether to "
                "migrate its data to SeaweedFS instead."
            )

    if not image_cached:
        if has_data:
            echo.error(
                f"'{image}' has been removed from Docker Hub and is no longer available locally "
                "either, so the existing MinIO data can neither be kept running nor migrated "
                "automatically. Restore the image locally (e.g. from a backup or another host) "
                "before installing again."
            )
            raise DockerError(f"'{image}' unavailable locally and remotely, with existing data")
        return False

    echo.warning(
        f"An existing MinIO container ('{image}') was found from a previous install. This exact "
        "image has been removed from Docker Hub, so it can no longer be pulled from scratch. We "
        "recommend migrating its data to SeaweedFS now - it's automatic, and the original MinIO "
        "data is only removed once the copy to SeaweedFS is verified to have fully succeeded."
    )
    if state.yes:
        return False

    if state.non_interactive:
        # `--non-interactive` is about automation, not consent to a destructive, one-way data
        # migration - unlike `--yes`, it must not silently trigger it. Default to keeping the
        # existing container (safe, reversible) and let the operator opt into migrating explicitly,
        # either interactively or with `--yes`.
        echo.warning(
            "Running non-interactively: keeping the existing MinIO container as-is instead of "
            "migrating automatically. Re-run interactively, or with `--yes`, to migrate its data "
            "to SeaweedFS."
        )
        return True

    return not echo.confirm(
        "Migrate the existing MinIO data to SeaweedFS now? Choosing 'no' keeps the current MinIO "
        "container running as-is, which depends on this image staying cached on this machine.",
        default=True,
    )


def _minio_credentials(old_service: dict[str, Any]) -> tuple[str, str]:
    """Read the old MinIO service's root credentials, falling back to its documented default."""
    raw_env = old_service.get("environment") or []
    # Compose's `environment:` can be list-form (`["KEY=VAL", ...]`, handled below) or mapping-form
    # (`{KEY: VAL}`) - a mapping's keys carry no `=`, so treating it as a list-of-pairs would
    # silently yield nothing and mask any non-default credentials with the "minioadmin" fallback.
    if isinstance(raw_env, dict):
        env_pairs = {str(key): str(value) for key, value in raw_env.items()}
    else:
        env_pairs = dict(pair.split("=", 1) for pair in raw_env if "=" in pair)
    user = env_pairs.get("MINIO_ROOT_USER") or env_pairs.get("MINIO_ACCESS_KEY") or "minioadmin"
    password = env_pairs.get("MINIO_ROOT_PASSWORD") or env_pairs.get("MINIO_SECRET_KEY") or "minioadmin"
    return user, password


def _command_argv(raw_command: object) -> list[str]:
    """Split a compose `command:` value into argv, accepting either its string or list form."""
    if isinstance(raw_command, list):
        return [str(part) for part in raw_command]

    return shlex.split(str(raw_command))


def _old_minio_mount_path(old_service: dict[str, Any]) -> str:
    """The old service's own bind-mount target for its `minio` volume, e.g. `/minio_data`.

    Matches on the volume's source being exactly `minio` - the fixed name `DOCKER_COMPOSE_MILVUS`
    always gives this service's data volume - rather than just taking the first volume entry with
    any target. Picking the first entry regardless of source would misidentify the mount path on a
    compose.yaml with an extra bind mount ahead of the data volume (e.g. a hand-added TLS cert
    mount): the migration container would then be launched against an empty path, `mc mirror` would
    report success after copying nothing, and the real backup - the only surviving copy once the
    real volume is wiped - would be deleted believing the migration succeeded.

    A volume spec can carry a trailing mode (e.g. `minio:/minio_data:ro`), so the target is the
    second `:`-separated segment, not everything after the first `:`.

    Raises:
        DockerError: If no `minio:<path>` entry is found, rather than guessing a fallback path for
            a destructive, one-way migration.
    """
    for volume in old_service.get("volumes", []):
        parts = str(volume).split(":")
        if len(parts) >= 2 and parts[0] == "minio" and parts[1]:
            return parts[1]

    raise DockerError(
        "Could not find the existing MinIO service's data volume mount (expected a 'minio:<path>' "
        "entry in its `volumes:` list) - aborting rather than guessing the wrong mount path for a "
        "destructive migration."
    )


def _migration_resource_names(old_volume_name: str) -> tuple[str, str, str]:
    """Derive this migration's container/staging-volume names from the old MinIO volume's own unique name.

    Fixed, host-global names would let two installs (different `--directory`, hence different
    `old_volume_name`) tear down and overwrite each other's in-flight migration if run concurrently
    on the same host - deriving from `old_volume_name`, which is already unique per directory,
    avoids that.
    """
    return f"{old_volume_name}-migrate-src", f"{old_volume_name}-migrate-dst", f"{old_volume_name}-migrate-tmp"


def ensure_no_orphaned_migration_volume(directory: Path) -> None:
    """Abort (`DockerError`) if a previous migration attempt left its temporary staging volume behind.

    That staging volume (see `_migration_resource_names()`) is only ever a disposable working copy
    of the original MinIO data - used so the relaunched legacy MinIO image gets a writable mount
    without the real `minio` volume ever being touched. It's not itself at risk of holding the only
    surviving copy of anything, but its deterministic name would otherwise collide with a later
    retry's `docker volume create`/`docker run --name`. Both branches of the keep-or-migrate
    decision call this before doing anything else - see `should_keep_existing_minio()` and
    `migrate_minio_data_to_seaweedfs()`.
    """
    old_volume_name = resolve_compose_volume_name(directory, "minio")
    if old_volume_name is None:
        return

    _, _, tmp_volume = _migration_resource_names(old_volume_name)
    if volume_exists_or_raise(tmp_volume):
        raise DockerError(
            f"A previous MinIO migration attempt left a temporary staging volume ('{tmp_volume}') "
            f"behind without cleaning up. It's safe to remove - the original MinIO data in "
            f"'{old_volume_name}' was never touched - with `docker volume rm {tmp_volume}`, then "
            "run the install again."
        )


def _wait_until_running(container: str) -> None:
    """Wait for `container` to report as running.

    These containers are started with a plain `docker run`, not through Compose, so they never get
    a container-level `HEALTHCHECK` - only `.State.Running` is meaningful here. Actual S3 readiness
    (the process being up doesn't mean its listener is accepting connections yet) is checked
    separately, via retrying the real `mc` call once both containers are running.
    """
    for _ in range(_HEALTH_POLL_ATTEMPTS):
        try:
            running = run(
                ["docker", "inspect", "--format={{.State.Running}}", container],
                capture_output=True,
                raises=DockerError,
            )
        except DockerError as exc:
            echo.debug(f"docker inspect failed for '{container}', retrying: {exc}")
        else:
            if (running or "").strip() == "true":
                return
        time.sleep(_HEALTH_POLL_INTERVAL_SECONDS)

    raise DockerError(f"Container '{container}' never started while migrating MinIO data.")


def _run_mc_mirror_with_retry(
    docker_network: str, src_user: str, src_password: str, src_container: str, dst_container: str
) -> None:
    """Mirror every object from the source to the destination, retrying until both S3 APIs answer.

    Both servers reporting as running doesn't mean their S3 listener is already accepting
    connections - retrying the real `mc` call is a more reliable readiness signal than polling
    Docker container state for something neither container actually reports.

    The `dst` alias always authenticates with `SEAWEEDFS_S3_ACCESS_KEY`/`SEAWEEDFS_S3_SECRET_KEY`,
    never `src_user`/`src_password` - the destination is a temporary SeaweedFS container loaded with
    `SEAWEEDFS_S3_CONFIG`'s identity (see `_launch_migration_containers()`), which only ever
    recognizes those fixed credentials. Using the *old* MinIO's real credentials for `dst` as well
    would authenticate against the wrong identity on any install with non-default MinIO credentials,
    making every such migration fail.
    """
    mc_script = (
        f"mc alias set src http://{src_container}:9000 {shlex.quote(src_user)} {shlex.quote(src_password)} && "
        f"mc alias set dst http://{dst_container}:9000 "
        f"{shlex.quote(SEAWEEDFS_S3_ACCESS_KEY)} {shlex.quote(SEAWEEDFS_S3_SECRET_KEY)} && "
        "mc mirror --overwrite src/ dst/"
    )
    command = ["docker", "run", "--rm", "--network", docker_network, "--entrypoint", "sh", _MC_IMAGE, "-c", mc_script]

    for attempt in range(1, _HEALTH_POLL_ATTEMPTS):
        try:
            run(command, capture_output=True, raises=DockerError)
        except DockerError as exc:
            echo.debug(f"mc mirror attempt {attempt}/{_HEALTH_POLL_ATTEMPTS - 1} not ready yet: {exc}")
            time.sleep(_HEALTH_POLL_INTERVAL_SECONDS)
        else:
            return

    # Final attempt: let a failure here raise on its own, instead of retrying forever.
    run(command, capture_output=True, raises=DockerError)


def _mc_object_count(docker_network: str, alias: str, user: str, password: str, container: str) -> int:
    """Return the total object count `mc du --json <alias>` reports across however many buckets exist.

    `mc du --json` prints one JSON line per bucket, not a single summary line - a fresh/empty
    install has zero buckets (zero output lines), and a real Milvus layout can have several. Summing
    every line's `objects` field, rather than assuming exactly one, keeps this correct for any bucket
    count. One `docker run` per side (instead of both `mc du` calls concatenated into a single
    output) is what makes that safe: with a shared alias-setup script and a variable number of lines
    per side, there would be no reliable way to tell where the source's bucket lines end and the
    destination's begin.
    """
    script = (
        f"mc alias set {alias} http://{container}:9000 {shlex.quote(user)} {shlex.quote(password)} && "
        f"mc du --json {alias}"
    )
    command = ["docker", "run", "--rm", "--network", docker_network, "--entrypoint", "sh", _MC_IMAGE, "-c", script]
    output = run(command, capture_output=True, raises=DockerError) or ""
    lines = [line for line in output.splitlines() if line.strip()]

    try:
        return sum(int(json.loads(line).get("objects", 0)) for line in lines)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise DockerError(f"Could not parse `mc du` output while verifying the migration: {output!r}") from exc


def _mirror_object_counts(
    docker_network: str, src_user: str, src_password: str, src_container: str, dst_container: str
) -> tuple[int, int]:
    """Return (source, destination) object counts, to verify a "successful" `mc mirror` actually moved data.

    `mc mirror` exits 0 both when it genuinely mirrors everything and when its source is empty for
    any other reason (e.g. the source container was launched against the wrong mount path - see
    `_old_minio_mount_path()` - or a credential mismatch hides every bucket). Between the real
    volume being wiped and the temp volume being removed, the temp volume is the only surviving
    copy of the original data, so a mismatch here must be caught before that removal happens.

    The `dst` side is always counted with `SEAWEEDFS_S3_ACCESS_KEY`/`SEAWEEDFS_S3_SECRET_KEY` - see
    `_run_mc_mirror_with_retry()` for why the destination never uses the old MinIO's own credentials.
    """
    src_objects = _mc_object_count(docker_network, "src", src_user, src_password, src_container)
    dst_objects = _mc_object_count(
        docker_network, "dst", SEAWEEDFS_S3_ACCESS_KEY, SEAWEEDFS_S3_SECRET_KEY, dst_container
    )
    return src_objects, dst_objects


def _verify_mirror_completed(
    docker_network: str, src_user: str, src_password: str, src_container: str, dst_container: str
) -> None:
    """Raise `DockerError` if the destination ended up with fewer objects than the source.

    See `_mirror_object_counts()` for why this check exists: a `mc mirror` that exits 0 is not on
    its own proof that anything was actually copied.
    """
    src_objects, dst_objects = _mirror_object_counts(
        docker_network, src_user, src_password, src_container, dst_container
    )
    if dst_objects < src_objects:
        raise DockerError(
            f"mc mirror reported success, but the destination only has {dst_objects} objects "
            f"versus {src_objects} on the source - refusing to treat this as a completed migration."
        )


def _cleanup_migration_containers(src_container: str, dst_container: str) -> None:
    """Best-effort teardown of the two migration containers, one failure at a time.

    Only the containers - never the temp volume, which may still hold the sole surviving copy of
    the user's data if the migration failed before `mc mirror` finished. Removing the temp volume
    is the caller's responsibility, done only once the migration has verifiably succeeded.
    """
    for container in (src_container, dst_container):
        try:
            run(
                ["docker", "stop", "-t", str(_STOP_TIMEOUT_SECONDS), container], capture_output=True, raises=DockerError
            )
        except DockerError as exc:
            echo.debug(f"Failed to stop '{container}' cleanly: {exc}")
        try:
            run(["docker", "rm", "-f", container], capture_output=True, raises=DockerError)
        except DockerError as exc:
            # These containers use deterministic, migration-derived names (see
            # `_migration_resource_names()`), so a leftover one collides with a later retry's
            # `docker run --name` and fails with a confusing "name already in use" error with no
            # link back to this cleanup failure - surfaced at warning level, like
            # `_remove_temp_volume()`'s cleanup failure, instead of silently at debug level.
            echo.warning(
                f"Failed to remove leftover migration container '{container}': {exc}. Remove it "
                f"manually with `docker rm -f {container}` before running the install again, or a "
                "retry may fail with a confusing 'name already in use' error."
            )


def _remove_volume(volume: str, *, context: str = "Migration succeeded") -> None:
    """Remove a no-longer-needed volume created in service of the migration.

    `context` prefixes the warning shown on removal failure (e.g. "Migration succeeded" once
    everything mirrored across and the legacy `minio` volume is being dropped, or "Migration failed
    before completion" when cleaning up disposable, unneeded volumes left over from a failed attempt).
    """
    try:
        run(["docker", "volume", "rm", volume], capture_output=True, raises=DockerError)
    except DockerError as exc:
        echo.warning(
            f"{context}, but failed to remove the now-unneeded volume '{volume}': {exc}. It can be "
            f"removed manually with `docker volume rm {volume}`."
        )


def _launch_migration_containers(
    docker_network: str,
    old_service: dict[str, Any],
    user: str,
    password: str,
    old_mount_path: str,
    tmp_volume: str,
    new_volume_name: str,
    seaweedfs_s3_config_path: Path,
    src_container: str,
    dst_container: str,
) -> None:
    """Launch the relaunched-legacy-MinIO source and fresh-SeaweedFS destination containers, plain `docker run`."""
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            src_container,
            "--network",
            docker_network,
            "-v",
            f"{tmp_volume}:{old_mount_path}",
            # Both credential spellings are set (rather than just the pair `_minio_credentials`
            # resolved from) so the relaunched container recognizes them regardless of which
            # spelling its own image version expects.
            "-e",
            f"MINIO_ROOT_USER={user}",
            "-e",
            f"MINIO_ROOT_PASSWORD={password}",
            "-e",
            f"MINIO_ACCESS_KEY={user}",
            "-e",
            f"MINIO_SECRET_KEY={password}",
            str(old_service["image"]),
            *_command_argv(old_service.get("command", "")),
        ],
        capture_output=True,
        raises=DockerError,
    )
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            dst_container,
            # The final compose service runs this same image as container/hostname "seaweedfs";
            # giving the migration container the same hostname keeps whatever peer/node identity
            # SeaweedFS persists to the volume under -dir consistent with the identity the real
            # service will present once it starts on that same data.
            "--hostname",
            "seaweedfs",
            "--network",
            docker_network,
            "-v",
            f"{new_volume_name}:/data",
            "-v",
            f"{seaweedfs_s3_config_path.as_posix()}:/etc/seaweedfs/s3_config.json",
            str(DOCKER_COMPOSE_MILVUS["seaweedfs"]["image"]),
            *_command_argv(DOCKER_COMPOSE_MILVUS["seaweedfs"]["command"]),
        ],
        capture_output=True,
        raises=DockerError,
    )


def _resolve_migration_volumes(directory: Path) -> tuple[str, str] | None:
    """Resolve the old `minio` and target `seaweedfs` volume names for a migration, or `None` if there's nothing to do.

    Returns `None` only for the legitimate no-op case: the old volume was resolved but is confirmed
    absent (a legacy compose.yaml with nothing ever written to it). Raises `DockerError` for every
    other reason `migrate_minio_data_to_seaweedfs()` can't safely proceed - see its own docstring
    for what each of those means.
    """
    old_volume_name = resolve_compose_volume_name(directory, "minio")
    if old_volume_name is None:
        raise DockerError(
            "Could not resolve the existing MinIO data volume's name (`docker compose config` "
            "failed). Aborting the migration rather than risk handing SeaweedFS a volume that "
            "still holds unmigrated MinIO data."
        )
    # `volume_exists_or_raise()`, not `volume_exists()`: a `False` here means "skip the migration
    # entirely, nothing to do" - the caller already decided to migrate, so an inspect failure must
    # raise instead of being silently treated as "no data", which would hand SeaweedFS a volume
    # still holding MinIO's on-disk format with no error or warning.
    if not volume_exists_or_raise(old_volume_name):
        return None

    # A previous attempt may have been interrupted before it could clean up its disposable staging
    # volume. Shared with `should_keep_existing_minio()` so the keep path gets the same guard.
    ensure_no_orphaned_migration_volume(directory)

    new_volume_name = resolve_compose_volume_name(directory, "seaweedfs")
    if new_volume_name is None:
        raise DockerError(
            "Could not resolve the target SeaweedFS data volume's name (`docker compose config` "
            "failed). Aborting the migration rather than guessing a volume name for the new service."
        )
    if volume_exists_or_raise(new_volume_name):
        raise DockerError(
            f"A SeaweedFS data volume ('{new_volume_name}') already exists even though this install "
            "still shows a legacy MinIO service - likely a previous migration attempt that didn't "
            f"finish cleanly. Inspect '{new_volume_name}', remove it with `docker volume rm "
            f"{new_volume_name}` once you've confirmed it holds nothing you need, then run the "
            "install again."
        )

    return old_volume_name, new_volume_name


def migrate_minio_data_to_seaweedfs(directory: Path, docker_network: str, old_service: dict[str, Any]) -> None:
    """Copy every object from the existing MinIO install into a fresh SeaweedFS volume.

    No-op (returns immediately) if `directory`'s compose.yaml no longer names a legacy MinIO
    image - either there's genuinely nothing to migrate, or this is a stale, replayed keep/migrate
    decision (e.g. from a persisted `suite install` state file) re-running against data that was
    already migrated by an earlier `apply()`. Re-checked here, independently of whatever the
    caller's already-resolved `InstallConfig` claims, so this function stays safe to call more than
    once for the same directory.

    No-op also if the old MinIO volume was resolved but is confirmed absent (Docker reports "no
    such volume") - a legitimate case for a legacy compose.yaml with nothing ever written to it.
    Raises `DockerError` instead if either volume's name couldn't even be resolved (e.g. `docker
    compose config` failed), or if the "does it exist" check itself failed for any other reason
    (daemon hiccup, permissions, wrong Docker context): neither is confirmation the volume is
    absent, and the caller already decided to migrate - silently doing nothing here would leave the
    real volume, still in MinIO's on-disk format, handed straight to SeaweedFS. Also raises if the
    target `seaweedfs` volume already exists - a legitimate legacy compose.yaml never references it,
    so its presence here means a previous migration attempt was interrupted before cleaning up.

    Otherwise: copies the old `minio` volume's raw bytes (read-only, never written to) into a
    disposable staging volume, runs the old MinIO image against that staging copy and a brand-new
    `seaweedfs` volume side by side, mirrors every object across via `mc mirror`, and confirms the
    destination's object count is at least the source's before trusting that result (`mc mirror`
    exits 0 even when it mirrored nothing). On success, the new `seaweedfs` volume holds the
    migrated data, the now-superseded `minio` volume and the staging volume are both removed, and
    the migration containers are cleaned up.

    On failure, the migration containers and any volumes created so far (the staging volume, and
    the new `seaweedfs` volume if it got that far) are cleaned up as disposable - the original
    `minio` volume is never touched until success is verified, so `DockerError` can always say the
    install is safe to simply retry.
    """
    if find_legacy_minio_service(directory) is None:
        return

    resolved_volumes = _resolve_migration_volumes(directory)
    if resolved_volumes is None:
        return
    old_volume_name, new_volume_name = resolved_volumes

    src_container, dst_container, tmp_volume = _migration_resource_names(old_volume_name)

    seaweedfs_s3_config_path = directory / "seaweedfs_s3_config.json"
    try:
        seaweedfs_s3_config_path.write_text(SEAWEEDFS_S3_CONFIG)
    except OSError as exc:
        raise DockerError(f"Unable to write {seaweedfs_s3_config_path.as_posix()}: {exc}") from exc

    user, password = _minio_credentials(old_service)
    old_mount_path = _old_minio_mount_path(old_service)

    echo.warning(
        "Migrating existing MinIO data to SeaweedFS - this briefly needs roughly the current "
        "storage's size again on disk (a staging copy of the original, plus the new SeaweedFS "
        "volume) until the migration is verified and the original MinIO volume is removed."
    )

    run(["docker", "volume", "create", tmp_volume], capture_output=True, raises=DockerError)

    # Tracks whether the new SeaweedFS volume has been created yet, so a failure's cleanup knows
    # whether there's a second volume to remove alongside the staging one.
    new_volume_created = False
    try:
        run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{old_volume_name}:/src:ro",
                "-v",
                f"{tmp_volume}:/dst",
                "alpine",
                "cp",
                "-a",
                "/src/.",
                "/dst/",
            ],
            capture_output=True,
            raises=DockerError,
        )

        run(["docker", "volume", "create", new_volume_name], capture_output=True, raises=DockerError)
        new_volume_created = True

        _launch_migration_containers(
            docker_network,
            old_service,
            user,
            password,
            old_mount_path,
            tmp_volume,
            new_volume_name,
            seaweedfs_s3_config_path,
            src_container,
            dst_container,
        )

        _wait_until_running(src_container)
        _wait_until_running(dst_container)
        _run_mc_mirror_with_retry(docker_network, user, password, src_container, dst_container)

        # `mc mirror` exits 0 both when it genuinely mirrored everything and when its source was
        # empty for an unrelated reason (wrong mount path, credential mismatch) - verify object
        # counts actually match before the old MinIO volume (still intact at this point) is removed
        # below. See `_old_minio_mount_path()` for the concrete scenario this catches.
        _verify_mirror_completed(docker_network, user, password, src_container, dst_container)
    except DockerError as exc:
        _cleanup_migration_containers(src_container, dst_container)
        _remove_volume(tmp_volume, context="Migration failed before completion")
        if new_volume_created:
            _remove_volume(new_volume_name, context="Migration failed before completion")
        raise DockerError(
            f"Migrating MinIO data to SeaweedFS failed: {exc}. The original MinIO data is untouched "
            f"in volume '{old_volume_name}' - simply run the install again to retry."
        ) from exc
    else:
        # Persisted the moment the mirror is verifiably done, ahead of the (best-effort,
        # non-critical) cleanup below and everything apply() still has to do afterwards - see
        # `_MIGRATION_MARKER_FILENAME`.
        try:
            _migration_marker_path(directory).write_text("")
        except OSError as exc:
            raise DockerError(
                f"Migration succeeded but failed to record it (writing "
                f"{_migration_marker_path(directory).as_posix()}: {exc}). Re-running the install "
                "now would incorrectly re-migrate already-migrated data - create that file "
                "yourself (empty is fine) before trying again."
            ) from exc
        _cleanup_migration_containers(src_container, dst_container)
        _remove_volume(tmp_volume)
        _remove_volume(old_volume_name)
