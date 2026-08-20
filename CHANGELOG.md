# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]
### Added
- `deepfellow server install` and `deepfellow suite install` now accept the admin user's name/email/password via `DF_SERVER_ADMIN_NAME`/`DF_SERVER_ADMIN_EMAIL`/`DF_SERVER_ADMIN_PASSWORD` environment variables, in addition to the existing `--admin-name`/`--admin-email`/`--admin-password` flags — so a scripted or CI install no longer has to put the password on the command line, where it would leak into shell history and process listings.

### Changed
- `deepfellow suite install` now reuses the built-in `workspace` templates that `infra install`/`server install` already expose via `--template`, instead of hardcoding its own copy of the same defaults (ollama service spec, chat/embedding/fast model names, Milvus config). No change in behavior or output for the end user.

### Fixed
- `server install --template` and `infra install --template` now also check `config.json` (best-effort, in addition to `.env`) before applying a template value, so a `--template` reinstall no longer silently overwrites a setting that migrated to `config.json` after the service's first start.
- `deepfellow suite install` now grants the workspace's project access to the three models (chat, embedding, fast) it just installed, via a follow-up call to the server's project-update endpoint right after workspace creation — previously the created project had no model access at all, contradicting the command's "ready-to-use workspace" promise.
- `deepfellow infra service install` and `deepfellow infra model install` now show the real failure reason on install error: both were reading the wrong SSE finish-event key (`detail`/`error`) instead of the `details` key the Infra Server actually sends, so a populated error message was silently dropped in favor of a fully generic failure message. When the server sends no details at all, the CLI now also points the user at `docker compose logs infra`.
- `deepfellow infra service install` no longer aborts when the target service is already installed on the Infra instance — the Infra API's `{"error": {"message": "... already installed"}}` response is now parsed into a readable message (previously fell back to printing the raw JSON body) and treated as a no-op, printing an informational message and exiting successfully instead of failing. This also makes `infra install --template`'s `post_start_actions` idempotent: a step targeting an already-installed service is skipped instead of aborting the whole install after 0 of N actions complete. (`infra model install` already reports success for a duplicate model in every case — Infra itself never returns an error for it.)
- CLI no longer crashes with a raw `KeyError` traceback instead of a readable error message when the DeepFellow Server reports an error in its newer `{"error": {"message": ...}}` format.
- `deepfellow infra install`/`server install` in `--non-interactive` mode now explains how to proceed (pass `--force-install` or remove the directory manually) when the target directory already exists, instead of aborting with no guidance.
- `deepfellow suite install --non-interactive` now reports every missing admin value (name, email, password) in a single error naming the exact `--admin-name`/`--admin-email`/`--admin-password` flags to pass, instead of aborting on just the first missing value with a message that didn't name a flag.

## [0.31.0] - 2026-08-06
### Added
- `deepfellow server install` gains a `--template <name-or-path>` option — a built-in `workspace` template or a YAML file supplying config defaults (port, infra connection, vector DB, embedding) and post-install actions (creating the admin user). Follows the same precedence as `infra install --template`: an explicit CLI flag wins, then a prior install's `.env`, then the template. When the template has post-install actions, the server is automatically started to run them, so it's left running afterward (unlike a plain `server install` with no template).
- `deepfellow server install` (with or without `--template`) now falls back to the `DF_INFRA_API_KEY` recorded in a local `infra install`'s own `.env` when `--infra-api-key` isn't passed, same as `suite install` already does, instead of leaving it unset.
- `deepfellow infra install --template <name>` — supply install-time defaults (port, DF_NAME, DF_INFRA_URL, docker network) and post-install actions from a built-in name or a YAML file; explicit CLI flags and a prior install's `.env` values still take precedence over the template.
- Both `--template` options validate the resolved template up front, rejecting an unrecognized top-level or `post_start_actions` key instead of silently discarding it.
- `deepfellow suite install` — provisions a complete DeepFellow workspace in one non-interactive-friendly run: infra install, infra start, infra service install (`ollama`, GPU spec), the three default models (chat, embedding, fast), server install (Milvus, `mxbai-embed-large`), server start, admin creation, login, and one call to the server's atomic workspace-creation endpoint (organization "Workspace", project "Default", API key "app"). All defaults are hardcoded in this version (no `--template` flag); it's a one-shot command with no `--resume`/progress tracking — a failure partway through must be recovered manually or by continuing with individual `infra`/`server` subcommands.
- `deepfellow infra service install` and `deepfellow infra model install` now show a live progress bar while a Docker image is pulled or a model is downloaded (e.g. multi-GB chat models), so long installs no longer look hung. When the server doesn't stream progress the command falls back to the previous single-response behaviour, and in `--non-interactive` mode it prints periodic percentage lines instead of a live bar.
- --set flag to `fields` command - prints fields in --set param=<value> friendly manner
- `deepfellow infra service install` now fetches the service spec from the API and interactively prompts for required fields before installing; `--set key=value` (repeatable) allows non-interactive configuration without knowing the JSON structure upfront
- `deepfellow infra service fields <service-name>` command — calls `GET /admin/services/{service-name}` and lists the configuration fields the service expects, printing each as `- {name}: {description} (default: {default})`; for `oneof` fields it also lists the available options (`available: ...`); exits with a clear error when the service is not found
- ollama-cloud installation option
- `deepfellow prune` command — full teardown in one step: prunes the DeepFellow Server and Infra stacks (`docker compose down -v` + removes their directories), wipes any remaining `~/.deepfellow/` files, and uninstalls the CLI package last. Each step tolerates a missing installation, and the destructive action is gated by a confirmation prompt respecting `--yes`/`--non-interactive`.
- `deepfellow --version` flag — prints the CLI version, plus the installed Infra and Server versions (each extra line shown only when that component is installed)
- Running `deepfellow` with no command now shows the DeepFellow banner with the current CLI version
- `deepfellow infra config get`/`deepfellow infra config set` — read and update Infra's dynamic configuration via `/admin/config`, applied without a restart
- `deepfellow server config get`/`deepfellow server config set` — same as above, for the Server
- `--secret` flag on all four `infra config`/`server config` `get`/`set` commands — reveal secret field values instead of masking them, via `/admin/config/{key}/reveal`
- `deepfellow server login --token` — register an already-obtained access token directly, skipping the email/password login flow
- `deepfellow infra install` gains `--allow-print-keys`/`--keep-compose-prefix`/`--keep-storage`/`--keep-metrics` flags (each with a `--no-...` counterpart) to pre-answer the corresponding confirmation prompts non-interactively, without needing full `--non-interactive` mode
- `--remove-images` flag on `deepfellow infra uninstall` — also removes the Docker images used by the DeepFellow Infra stack (including the image recorded in `DF_INFRA_IMAGE`); off by default, so a plain `deepfellow infra uninstall` keeps images as before
- `deepfellow cli update` no longer reports failure (exit code 1, no success message) after a successful upgrade; it now exits 0 and prints "updated successfully" when the upgrade completes, and only errors out when the upgrade command actually fails.
- Fixed `--non-interactive` failing with "Please provide the value in args" when a CLI argument value equals the Typer default (e.g. `--mongodb-database-name deepfellow` during `server install`).
- Fixed server organization delete: wrong success message and added --yes parity.
- `deepfellow infra service` and `infra model` commands no longer exit with a raw traceback on connection timeouts or other transport errors — every Infra API call now fails with a readable error message.
- `deepfellow infra install` now correctly offers to keep a previously configured storage directory when reinstalling over an existing install; the check was silently broken and always regenerated the default storage path.
- `deepfellow server install` now rejects an invalid `--otel-url` and an empty Infra API key with a clear error instead of silently writing them to `.env`.
- `deepfellow infra install`/`update` and `server install`/`update` now print a warning when the registry token needed to resolve the newest image tag can't be obtained, before falling back to `:latest`; this previously failed silently.

### Changed
- `deepfellow cli update` now resolves its upgrade command from the `DF_UPDATE_COMMAND` value stored in config (written by `install.sh` at install time), instead of always probing the package manager; existing installs keep working via detection fallback, and the resolved command is written back to config on first run. `install.sh` now records `DF_UPDATE_COMMAND` alongside `DF_UNINSTALL_COMMAND`, so `cli update` also works for pip/pip3 installs.
- `infra connect` no longer takes the mesh key as a required command-line argument; in interactive mode it prompts for the key with masked (password-style) input, so the secret no longer leaks into the screen, shell history, or process list. The key can still be passed as an argument for scripting and `--non-interactive` runs.
- `df infra/server install` both have switched order of questions. Docker Network prompt appears sooner.
- Infra API error messages are now consistent across all `deepfellow infra service`/`infra model` commands and surface the server's error `detail` instead of a raw JSON response body.
- Renamed the `--server` option to `--url` on all Server/Infra API-calling commands
  (`--server` was overloaded — it's also the Docker container name, and in `infra` it
  meant the Infra address, not the Server). **Breaking:** no alias — `--server` now errors.
- Direct dependencies pinned at pre-1.0 versions (`httpx`, `deptry`, `ruff`) now use `~=` instead
  of `>=`, so a future minor release can no longer be picked up silently; only patch updates are
  allowed automatically. See `docs/adr/00001-pin-pre-1.0-dependencies.md`.
- `just test` now fails the build if total test coverage drops below 100%, instead of silently
  allowing untested code to ship.

### Fixed
- `deepfellow infra install` no longer creates the docker network before all setup questions have been answered; aborting the install partway through no longer leaves an orphaned docker network behind.
- `deepfellow server install` no longer creates the docker network before all setup questions have been answered; aborting the install partway through no longer leaves an orphaned docker network behind.
- `deepfellow server install` no longer crashes with a raw `TypeError` when it fails; the failure is now reported with the usual error message.
- `deepfellow infra install`/`server install` no longer print a false "installed" success message when `docker compose pull` fails (registry errors, auth failures, disk full); the failure is now reported and the install aborts.
- `deepfellow infra install`/`server install` no longer crash with a raw traceback if writing the `.env`/compose files fails (e.g. disk full, permission denied); the failure is now reported cleanly instead.
- `deepfellow server install` no longer crashes with a raw traceback if saving the default server directory fails after an otherwise successful install.
- `deepfellow server install` no longer crashes on a corrupted or deeply-nested `DF_PLUGINS_SETUP` value in an existing `.env` file; it's now reported as an invalid value like any other malformed input.
- `deepfellow infra service install`/`infra service fields`/`infra model install` no longer permanently save a bad `--url` or Infra Admin API Key to local config before confirming it actually works; the value is now only persisted once a request against it succeeds.
- `server install`/`server reconfigure` with a custom Milvus vector database now correctly keeps an explicitly-provided `--vectordb-username`/`--vectordb-password`, instead of silently overriding it with a stale value from an existing `.env` file.
- `server install` no longer crashes with an unhandled `OSError` if creating the storage/plugins bind-mount directories fails (e.g. permission denied); it now shows a clear error message instead.
- `deepfellow suite install` no longer crashes with a raw traceback when a step fails; failures now exit cleanly with a readable error message, matching `infra install`/`server install`.
- `just check`'s `mypy`/`ruff` recipes now scan the same paths (`deepfellow/ tests/`) as the GitLab CI pipeline, so type and lint errors introduced only under `tests/` are caught locally instead of surfacing as CI-only failures.
- `deepfellow server start`/`restart`/`update`/`env set` (and `suite install`) now detect a MongoDB authentication failure caused by a stale `mongo` Docker volume from a previous install (e.g. after `server uninstall` followed by a fresh `server install`) and print a specific remediation hint, instead of the generic "container server is unhealthy" message.
- `deepfellow server install`, when no matching MongoDB admin credentials are found in `.env` (fresh or missing directory), now detects a pre-existing `mongo` Docker volume from an earlier install and asks whether to remove it before generating new credentials, instead of silently installing credentials that are guaranteed to mismatch it and crash-loop; declining aborts the install without touching the volume. `--yes` skips the prompt and removes the volume automatically.

## [0.8.0] - 2026-06-19

### Added
- `install.sh --dev` flag — installs from `main` on GitLab instead of the latest GitHub release, enabling a pre-release smoke test of the official install path
- CI smoke-test jobs — run the real `install.sh` against the current checkout under each supported package manager (uv, pipx, pip) and then start the CLI (`deepfellow version` / `deepfellow --help`); gate the release stage so a broken install, dispatch regression, or startup crash blocks the GitHub push
- `infra restart` and `server restart` commands — restart the whole Docker Compose stack for their scope in one step (stop then start), instead of running `stop` and `start` manually
- `deepfellow otel logs` command — tails the local OpenTelemetry collector (installed via `server install --otel-local`) with `-f`/`--follow` and `-n`/`--tail`, consistent with `server logs`; reports clear errors when the collector is not installed or not running
- `infra env set` and `server env set` now prompt to restart the stack after updating the `.env` file, so the new value takes effect immediately without a manual restart
- `server install` and `server update` now automatically select the newest semver-tagged image from the registry (e.g. `v1.2.3`) instead of `:latest`, matching the existing behaviour of `infra install` and `infra update`; falls back to `:latest` if the registry is unreachable
- Unit tests for `infra disconnect` covering directory checks, service-running guard, confirmation flow, env variable handling, and disconnect execution paths
- Unit test coverage for infra install raised to 100%
- Unit test coverage for infra start raised to 100%
- Unit tests for `server create-admin` command
- Added http(s) to ws(s) converter which allows connecting Infra even with http(s) URL provided.
- `deepfellow uninstall` command — uninstalls the CLI using the detected package manager (`uv tool`, `pipx`, or `pip`); falls back to the `DF_UNINSTALL_COMMAND` value stored in config for custom setups
- `server install` and `server reconfigure` now prompt to choose between dense and sparse embedding type; selecting sparse automatically uses the BGE-M3 model
- `DF_MONGO_PORT` — configurable host port for the local MongoDB instance (default `27017`); `server install` now publishes MongoDB on the specified port instead of only exposing it within the Docker network


### Changed
- `server install` now frames the MongoDB and vector database prompts as a local install by default ("Install a local MongoDB for DeepFellow Server?" / "Install a local vector database for DeepFellow Server?", default Yes), so accepting the defaults produces a working local stack; connecting an existing/external instance now requires answering No and providing its connection details
- `server create-admin` now prints the password requirements up front and re-prompts in a loop on an invalid password instead of exiting, matching the existing behaviour of the name and email prompts; `--non-interactive` still exits with code 1 on a missing or invalid password
- Increased timeout when connecting Infras to 60 seconds.

## [0.7.0] - 2026-06-11

### Added
- `deepfellow infra service list` command — calls `GET /admin/services` and displays the installed service backends
- `just deptry` command — runs [`deptry`](https://deptry.com) to detect imports used in source but not declared as explicit dependencies in `pyproject.toml`; integrated into `just check` and the CI/CD pipeline

### Changed
- Removed unused symbols from common modules: `merge_services()`, `ConfigValidationError`, `check_directory_exist()`, `validate_config()`, `Infras` dataclass, and legacy constants `DF_INFRA_REPO`, `DF_SERVER_REPO`, `API_ENDPOINTS`; corresponding tests deleted
- `server install` and `server opentelemetry` now use `DF_OTEL_EXPORTER_OTLP_ENDPOINT` as the default OTel URL instead of `None`

### Fixed
- `server uninstall` and `infra uninstall` no longer crash with `PermissionError` on Docker-owned directories; they now warn the user, ask to retry with `sudo rm -rf` (auto-confirmed with `--yes`), and print a clear manual-removal message if sudo is declined or unavailable
- Server `compose.yaml` now forwards `DF_PLUGINS_SETUP` and `DF_LOG_LEVEL` to the server container, so `server env set PLUGINS_SETUP ...` actually reaches the server (previously plugins like `DFAnonymizePlugin` never saw their configuration); `server install` writes defaults (`{}` / `INFO`), preserves existing values on reinstall and validates both before writing
- `server install --otel-local` installs a local debug-only OpenTelemetry collector non-interactively (mutually exclusive with `--otel-url`); previously the local collector could only be enabled through interactive prompts

## [0.6.0] - 2026-06-10

### Added
- `server install` and `server reconfigure` now offer a debug-only OTel collector mode: when the user opts to run OTel locally, a new prompt asks whether to export to Elasticsearch (default: No); answering No starts the `otel-collector` without any Elasticsearch dependency

### Changed
- CLI runtime flags now come from an internal `AppState` singleton instead of the Click context, so the CLI runs on Typer 0.26.x (previously pinned to 0.16.x to avoid a startup crash)

### Fixed
- `server env info` now displays variable names with the `DF_` prefix (e.g. `DF_SERVER_PORT`) to match the names Docker/shell require, while `server info` keeps showing runtime values without the prefix

## [0.5.0] - 2026-06-03

### Added

- Added `--api-key` option to `infra service install` to support remote services requiring an API key (e.g. `claude`)
- Added per-service spec building for known cloud services (`claude`, `google`, `openai`, `sindri`); required fields with defaults (e.g. `anthropic_version`) are applied automatically

### Fixed

- `deepfellow cli update` command — upgrades the CLI using the detected package manager (`uv tool`, `pipx`, or `pip`)
- `df infra connect` now verifies the WebSocket mesh connection is live before reporting success, with multi-stage polling of `/admin/mesh/topology`, detection of outdated images (HTML response) and legacy parent API (Docker log fallback), and a warning when a localhost URL is used
- Increased maximum password length from 19 to 128 characters

## [0.4.0] - 2026-05-28

### Fixed
- pin `typer~=0.16.0` to prevent crash on startup caused by Typer 0.26+ vendoring its own Click fork with a separate context stack, breaking `click.get_current_context()` calls

### Fixed
- `server reconfigure` now preserves existing MongoDB admin credentials instead of regenerating them

### Added
- `infra info` and `server info` now display styled output: `DF_` prefix stripped, sensitive values masked by default (`--secret` to reveal), undefined variables shown as `undefined`, and `--doc` flag for per-variable descriptions
- Added unit tests for `infra stop` command
- Added unit tests for `infra update` command
- Added unit tests for `infra ssl-on` command (100% branch coverage)
- Added unit tests for `infra install` command

## [0.3.1] - 2026-05-21

- fix: `infra install` — docker compose pull failure now shows error message
- fix: `server login` — fix KeyError crash when server response lacks `refresh_token`

## [0.3.0] - 2026-05-20

- `deepfellow infra prune` — removes all infra containers, volumes, and files
- `deepfellow server prune` — removes all server containers, volumes, and files

## [0.2.2] - 2026-05-19

- fix release process

## [0.2.1] - 2026-05-19
- styling for the `echo.choice`
- `echo.choice` now handles `from_args`
- `install --directory` sets storage path automatically
- vector database selection text styling consistency
- create random credentials for
  - metrics endpoint
  - default mongo
  - default milvus
- fix for non interactive:
  - server
  - infra civitai key
  - infra hugging face key
- server install now persists OTEL data between runs
- fix: mongo compatibility on some systems
- fix: password minimum length enforced to 10 characters
- refresh token automatically on server login
- bind docker ports to localhost only (do not expose publicly)
- recommend rootless Docker mode for infra installs
- add healthcheck for Qdrant container
- fix: too wide permissions on mongo database
- fix: outdated Docker Compose service names

## [0.2.0]

- Qdrant as a default vector database
- `deepfellow infra status` / `deepfelow server status` - displays container status and resource usage
- Added non-interactive mode support with `--non-interactive` flag for all commands

## [0.1.0] - 2026-01-16

### Added

- Initial release of DeepFellow CLI
- Server management commands:
  - `deepfellow server install` - Install DeepFellow Server with docker
  - `deepfellow server start` - Start DeepFellow Server
  - `deepfellow server stop` - Stop DeepFellow Server
  - `deepfellow server update` - Update DeepFellow Server
  - `deepfellow server login` - Login user and store the token in the secrets file
  - `deepfellow server create-admin` - Create admin
  - `deepfellow server password-reset` - Password reset
  - `deepfellow server opentelemetry` - Connect to Open Telemetry
  - `deepfellow server project` - Manage Projects
  - `deepfellow server organization` - Manage Organizations
  - `deepfellow server env` - Manage DeepFellow Server environment variables
  - `deepfellow server info` - Display environment configuration
- Infra management commands:
  - `deepfellow infra install` - Install infra with docker
  - `deepfellow infra start` - Start DeepFellow Infra
  - `deepfellow infra stop` - Stop DeepFellow Infra
  - `deepfellow infra update` - Update DeepFellow Infra
  - `deepfellow infra ssl-on` - Switch on the SSL
  - `deepfellow infra connect` - Connect two Infras together
  - `deepfellow infra disconnect` - Disconnect infra
  - `deepfellow infra service` - Manage DeepFellow Infra services
  - `deepfellow infra model` - Manage DeepFellow Infra models
  - `deepfellow infra env` - Manage Infra environment variables
  - `deepfellow infra info` - Display environment configuration
- Support for Docker Compose features
- Environment variable management for both server and infra
- OpenTelemetry integration support for server installations
- Project and organization management capabilities
- Password reset functionality
- Admin creation support
- Service and model management for infra
- SSL configuration support
- Environment configuration and management
- `deepfellow service uninstall` get `--purge` option to clear its files
- `deepfellow model uninstall` get `--purge` option to clear its files
