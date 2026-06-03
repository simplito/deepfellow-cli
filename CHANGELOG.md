# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
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
