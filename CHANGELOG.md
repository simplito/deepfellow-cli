# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed
- `server install` sets up Milvus 2.6.25, etcd 3.5.34, SeaweedFS 4.48, Qdrant 1.19.2 and MongoDB 8.2.12; existing installs keep their versions unless reinstalled
- README quickstart installs the same models as `suite install` (`gemma4:e4b`, `mxbai-embed-large`) and lists `gemma3:1b` as a lightweight option

### Removed
- Outdated `docs/INSTALL.md`; installation is documented in `README.md`

### Fixed
- Milvus installs start up to a minute faster
- FalkorDB no longer crashes on restart once the knowledge graph holds embeddings: `server install` sets up FalkorDB 4.22.2 (existing installs: reinstall)
- `server install` can migrate legacy MinIO-backed Milvus data to SeaweedFS again

## [0.36.0] - 2026-10-21

### Added
- `changelog-check` CI job needs an `[Unreleased]` entry (skip: `[skip changelog-check]` in MR title).
- `--bind-address` (`--server-bind-address`/`--infra-bind-address` in `suite install`) publishes the API port on one address only
- `deepfellow suite install` now prints the estimated VRAM of the models its template installs before it asks for anything, so you can stop before a long install on a GPU that is too small. The figures cover model weights only; the context window and runtime overhead come on top.
- `deepfellow server install` now warns when it sets up a local Qdrant: Qdrant keeps its index in memory and can stop responding once the data grows past about 5 GB, so it is not suited for large data volumes. The warning suggests Milvus (`--vectordb-type milvus`) instead.

### Changed
- `infra connect`/`disconnect` help now calls the network a Mesh
- `server env set DF_RABBITMQ_*` no longer writes `.env` when the server manages RabbitMQ settings; use `server config set`
- CLI commands reach the local Server and Infra at their bind address instead of `localhost`
- `--yes` now applies to every yes/no question, including `server * delete` and `server project archive`

### Fixed
- `server install` publishes MongoDB and `--dev` ports on 127.0.0.1 only; undo with `server env set INTERNAL_BIND_ADDRESS ""`

## [0.35.0] - 2026-10-15

### Added
- `infra model update`/`versions` and `infra service update`/`versions`
- `server nightshift` commands to configure and inspect the Nightshift worker
- `infra model install --spec` for a model's install configuration
- `suite install --allow-rootful`
- `suite install` and `infra install --template workspace` also install Doc Chunker and faster-whisper

### Changed
- `server install` and `suite install` always set up RabbitMQ and Nightshift; `server update` adds them to older installs
- `server status`/`restart`/`update`/`logs` also cover Nightshift
- `config get`/`set` print `key: value` lines instead of raw JSON
- `suite install` no longer installs `qwen3.5:4b`

### Fixed
- Secret and `.env` files are created with owner-only permissions
- Root MongoDB installs are moved to a least-privilege account
- Rootful Docker warning also covers `DOCKER_HOST`
- `server update` and `infra update` say "already up to date" instead of re-pulling

## [0.34.1] - 2026-09-25

### Added
- `infra model list <service_name>` lists a service's models
- `server project create`/`update` accept `--webhook-url` and `--webhook-secret`
- `suite install --template <name>`

### Changed
- `infra install` prompts use readable names instead of `DF_*` variables

### Fixed
- `.env` values with backslashes, quotes or newlines are no longer corrupted
- `infra`/`server` commands check up front that Docker is usable
- `suite install` runs the template's `post_start_actions`
- Command groups without a subcommand show `--help` instead of an error

## [0.34.0] - 2026-09-16

### Fixed
- `suite install` and `server install --template` no longer crash with `TypeError` against servers that return `webhook_url`

## [0.33.0] - 2026-09-11

### Added
- `server toolbox` and `server tool` commands
- `suite install --resume` continues an interrupted run

### Changed
- Milvus object storage uses SeaweedFS instead of MinIO; existing installs are offered a migration
- `suite install` and `--template` installs ask all prompts up front

### Fixed
- Milvus installs no longer fail on the removed MinIO image
- `suite install --resume` repairs deleted directories and stopped containers
- `infra service install` and `infra model install` retry while an earlier install is running

## [0.32.0] - 2026-09-01

### Added
- `infra mcp` commands to manage MCP servers on Infra
- `server project update`
- More `suite install` flags and `DF_SERVER_ADMIN_*` variables for scripted installs

### Changed
- **Breaking:** Knowledge Graph uses FalkorDB instead of Neo4j; `--neo4j-*` options became `--falkordb-*`

### Fixed
- Install commands show real backend errors and an activity indicator
- `infra service install` skips an already installed service
- `infra install --template` no longer overrides explicit CLI flags
- `server install` no longer fails with "Invalid DF_PLUGINS_SETUP" on reinstall

## [0.31.0] - 2026-08-06

### Added
- `--template` for `infra install` and `server install`
- `suite install` provisions a complete workspace in one run
- `infra service fields` and prompts or `--set` for required service fields
- `infra config` and `server config` commands, `server login --token`
- `deepfellow prune` and `deepfellow --version`
- Live progress bar for service and model installs

### Changed
- **Breaking:** `--server` renamed to `--url`
- `infra connect` prompts for the mesh key instead of taking it as an argument

### Fixed
- `infra install` and `server install` no longer leave an orphaned Docker network or crash on failures
- `cli update` exits 0 after a successful upgrade

## [0.8.0] - 2026-06-19

### Added
- `infra restart`, `server restart`, `otel logs` and `deepfellow uninstall`
- `env set` offers to restart the stack
- `server install`/`update` pick the newest semver image instead of `:latest`
- Dense or sparse embedding choice; `DF_MONGO_PORT`; `install.sh --dev`

### Changed
- `server install` sets up MongoDB and the vector database locally by default
- Timeout for connecting Infras raised to 60 seconds

## [0.7.0] - 2026-06-11

### Added
- `infra service list` shows installed service backends

### Changed
- `server install` and `server opentelemetry` default to `DF_OTEL_EXPORTER_OTLP_ENDPOINT` as the OTel URL

### Fixed
- `server uninstall` and `infra uninstall` handle Docker-owned directories by offering a `sudo rm -rf` retry
- `server` container now receives `DF_PLUGINS_SETUP` and `DF_LOG_LEVEL`
- `server install --otel-local` installs the local OTel collector non-interactively

## [0.6.0] - 2026-06-10

### Added
- `server install` and `server reconfigure` ask whether the local OTel collector exports to Elasticsearch (default: No)

### Changed
- CLI runs on Typer 0.26.x (previously pinned to 0.16.x)

### Fixed
- `server env info` shows variable names with the `DF_` prefix

## [0.5.0] - 2026-06-03

### Added
- `infra service install --api-key` for remote services that need one (e.g. `claude`)
- Known cloud services (`claude`, `google`, `openai`, `sindri`) get their install spec built automatically
- `cli update` upgrades the CLI using the detected package manager

### Changed
- Maximum password length raised from 19 to 128 characters

### Fixed
- `infra connect` verifies the mesh connection is live before reporting success

## [0.4.0] - 2026-05-28

### Added
- `infra info` and `server info` show styled output with masked secrets (`--secret` reveals) and `--doc` descriptions

### Fixed
- CLI no longer crashes on startup with Typer 0.26+
- `server reconfigure` keeps existing MongoDB admin credentials

## [0.3.1] - 2026-05-21

### Fixed
- `infra install` shows the error when `docker compose pull` fails
- `server login` no longer crashes with `KeyError` when the response lacks `refresh_token`

## [0.3.0] - 2026-05-20

### Added
- `infra prune` and `server prune` remove all containers, volumes and files

## [0.2.2] - 2026-05-19

### Fixed
- Release process

## [0.2.1] - 2026-05-19

### Added
- `install --directory` sets the storage path automatically
- Random credentials for the metrics endpoint, default MongoDB and default Milvus
- `server install` keeps OTel settings between runs
- Rootless Docker is recommended for Infra installs
- Health check for the Qdrant container

### Changed
- Docker ports are bound to localhost only
- Server login refreshes the token automatically
- Minimum password length is 10 characters
- Consistent styling for choice prompts and vector database selection

### Fixed
- `--non-interactive` for `server` and `infra` Civitai/Hugging Face keys
- MongoDB compatibility on some systems and overly wide database permissions
- Outdated Docker Compose service names

## [0.2.0]

### Added
- Qdrant as the default vector database
- `infra status` and `server status` show container status and resource usage
- `--non-interactive` flag for all commands

## [0.1.0] - 2026-01-16

### Added
- Initial release of DeepFellow CLI
- `server` commands: `install`, `start`, `stop`, `update`, `login`, `create-admin`, `password-reset`, `opentelemetry`, `project`, `organization`, `env`, `info`
- `infra` commands: `install`, `start`, `stop`, `update`, `ssl-on`, `connect`, `disconnect`, `service`, `model`, `env`, `info`
- Docker Compose, OpenTelemetry and SSL support
- `service uninstall` and `model uninstall` get `--purge` to remove files
