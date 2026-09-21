# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- `deepfellow server project create`/`update` now accept `--webhook-url`/`--webhook-secret` to set a Project's webhook URL and signing secret, and `webhook_secret` is now included (masked as `*****`) when a Project is displayed - previously there was no way to view or set a Project's webhook secret through the CLI.
- `deepfellow infra model list <service_name>` - lists the models available on an infra service (id, type, size, description, and installed status), so a model name no longer has to be guessed or looked up via the API/WebUI before running `infra model install`. `--installed`/`--no-installed` filters the list to only installed or only not-installed models.

### Fixed
- `infra`/`server` commands that run `docker`/`docker compose` (`start`, `stop`, `restart`, `update`, `logs`, `ssl-on`, `env set`, and `infra connect`/`disconnect`) now validate up front that docker is installed, running, and usable, and give a clear DeepFellow error message instead of a raw docker error when it isn't - previously only `install`, `status`, `prune`, and `uninstall` did this check. The check itself (`assert_docker`) now also verifies the `docker compose` plugin is present, not just the `docker` binary.
- Every command group (`infra`, `server`, `cli`, and their subgroups such as `infra service`, `infra env`, `server organization`, etc.) invoked without a subcommand now prints its `--help` listing instead of a "Missing command." error - e.g. `deepfellow infra` now shows the available `infra` commands directly.

## [0.34.0] - 2026-09-16
### Fixed
- `deepfellow suite install` (and `server install --template`) no longer crashes with an unhandled `TypeError` during the workspace-creation step against a server that returns a `webhook_url` field on project objects - the CLI's `Project` model now accounts for it.

## [0.33.0] - 2026-09-11
### Added
- `deepfellow server toolbox` (`create`/`list`/`get`/`update`/`delete`) and `deepfellow server tool` (`create`/`list`/`get`/`update`/`delete`, nested under a toolbox) — manage Toolboxes and the Tools within them via the DeepFellow Server's `/toolboxes` REST API. A tool's definition (`mcp`, `infra-mcp`, `custom-mcp`, `file_search`, `image_generation`, or `websearch`) is passed as JSON via `--config <path>` or piped on stdin. Both command groups take `project_id` and an optional `--organization-id`, mapped to the `OpenAI-Project`/`OpenAI-Organization` headers the server requires.
- `deepfellow suite install` now tracks its progress across its 14 constituent steps (infra configuration, server configuration, infra install, infra start, infra service install, 3x infra model install, server install, server start, create admin, server login, workspace creation, grant model access), persisting completion to a state file after each step. A `--resume` flag continues a previous, incomplete run from the first unfinished step instead of requiring manual recovery via individual `infra`/`server` subcommands — resolving the known limitation called out in the 0.31.0 entry for `suite install`.
- `deepfellow suite install` now warns, once per run, that the admin password is being saved in plain text to its state file (so `--resume` can reuse it without re-prompting) and reminds the user it's removed automatically on full success, or should be removed by hand if the run is abandoned.

### Changed
- `server install`'s default Milvus object storage now uses SeaweedFS's S3 gateway instead of MinIO - `minio/minio` has removed most historical release tags from Docker Hub, so the previously pinned image can no longer be pulled and Milvus installs were failing. An existing install with data under the old MinIO container is offered an automatic migration (or the option to keep the old container as-is) the next time `server install`/`suite install` runs against that directory; if the old container is still running, the install now asks you to stop it (`deepfellow server stop`) before continuing.
- `infra install --template` and `server install --template` now collect their template's post-start-action prompts up front, before any of those actions runs, instead of asking and acting one action at a time. This covers every post-start prompt there is: for `server install --template`, all `server.create_admin` actions ask for their missing admin name/email/password first, and only then is any admin account created; for `infra install --template`, every model install's connection prompt and every service install's spec-field prompts (built from a field list fetched from the now-running infra) are asked first, and only then does any model or service actually get installed. What is asked, and the installation logic itself, are unchanged - only when the prompts fire.
- `create_admin` (used by `server create-admin`, `suite install`, and `server install --template`'s post-install action) is now internally split into a credential-resolution step and an account-creation step, with no change in behavior for any existing caller — groundwork for `server install --template` to collect admin credentials before running any installation action.
- `deepfellow suite install` (without `--resume`) no longer aborts with "pass --resume or remove the file" when an unfinished previous run's state file exists — it now asks for confirmation before discarding that stale progress (skippable with `--yes`), warning specifically about an unrecoverable workspace API key when one was already created; declining continues the previous run in place instead, exactly as `--resume` would, so nothing is lost to a forgotten flag. In `--non-interactive` mode, where there's no prompt to fall back on, it defaults to discarding and starting fresh, matching the documented "no `--resume` = fresh" behavior for every invocation, interactive or not. `deepfellow suite install --help` is updated to match - it previously still described the old, unconditional "always starts fresh" behavior.
- `deepfellow suite install --resume` no longer prints "Updated .../config."/"Updated .../secrets." before every ollama service/model install step — these repeat the exact same, already-confirmed connection info on every one of the (up to 4) calls, which is just noise on a resumed run. `infra service install`/`infra model install` gained a `quiet` parameter for this (defaulting to `False`, so a plain, non-suite-install run of either command is unaffected). This is now also applied when a bare (non `--resume`) rerun hits the discard-previous-run prompt and the user declines it — that path continues the previous run exactly as `--resume` would, so it's quieted the same way, not just runs where `--resume` was passed explicitly.
- `deepfellow suite install --resume` no longer prints a "Resuming suite install: steps already completed (...); continuing from step N/12." summary line before the first step runs — each step already announces "... already completed, skipping." (or reruns visibly) as it's reached, making the upfront summary redundant.
- `infra model install`'s internal `install()` is now split into a connection-resolution step (`resolve_connection()`) and an apply step (`apply_install()`: performs the install call), with no change in behavior for any existing caller — groundwork for the same upfront-config work as the `infra service install` split.
- `infra service install`'s internal `install()` is now split into a spec-building step (`build_spec()`: resolves the connection and prompts for/validates the install spec) and an apply step (`apply_spec()`: performs the install call), with no change in behavior for any existing caller — groundwork for `suite install`'s upfront-config work and `infra install --template`'s post-start reordering.
- `ensure_directory()` (used internally by `infra install`/`server install`) now accepts a pre-resolved `overwrite` decision instead of always prompting inline when the target directory already exists — groundwork for a future upfront confirmation step; `infra install`'s/`server install`'s own current behavior is unchanged.
- `deepfellow suite install` now resolves and asks for all infra and server configuration up front, in two new steps ("infra configuration"/"server configuration"), before any installation action runs. Previously, server's configuration prompts (MongoDB, vector DB, OTel, FalkorDB, etc.) only appeared partway through the run, after infra was fully installed, started, and had its models installed.

### Fixed
- `server install`'s default Milvus object storage service is healthy again - the `minio/minio:RELEASE.2024-12-18T13-15-44Z` image it depended on was removed from Docker Hub, so installs (and self-healing repairs) that used the default vector DB setup were failing to pull it. See the SeaweedFS migration entry above.
- `deepfellow suite install --resume` no longer re-enters `infra install`/`server install`'s directory-exists guard (which would silently merge into, and print confusing "already configured it" template-merge warnings about, whatever unrelated `.env` happens to already live in `~/.deepfellow/infra`/`~/.deepfellow/server`) just because *some* state file exists on disk. It's now re-entered only for the specific step (`infra install` or `server install`) this suite install run itself already completed — each tracked, and force-re-entered, independently of the other.
- `deepfellow suite install --resume` no longer trusts a step's persisted "completed" flag blindly for anything that can drift out of sync with reality: `infra install`/`server install` now re-check that their directory and `.env` still exist, `infra start`/`server start` now re-check the container is actually running (`docker compose ps`) and restart it if not, and `infra service install`/model installs/`create admin`/`grant model access` now always re-attempt (relying on their own already-proven idempotency) instead of skipping outright. Previously, deleting `~/.deepfellow/infra` (or removing a container) after a step succeeded left `--resume` believing everything was still up, skipping the steps that would have fixed it, and failing later with a misleading connection error instead of self-healing.
- `deepfellow suite install --resume` self-healing a deleted infra directory no longer regenerates `DF_INFRA_API_KEY` at all - it now reapplies the exact configuration already resolved and persisted for this run, instead of resolving a fresh one. This also means server no longer needs to be force-repaired just because infra was; server's own repair is now solely about its own directory's integrity.
- `deepfellow suite install --resume` self-healing a deleted infra directory (with the container itself never actually stopped, e.g. an `rm -rf` rather than `infra uninstall`) no longer leaves infra's own, still-running container holding the old, now-dead `DF_INFRA_API_KEY`. `infra start`'s "still done" check previously only asked whether the container was running, not whether infra needed repair, so the freshly-reprovisioned key on disk was never actually loaded into the container - the same gap the server-side fix above closed, just on `infra start` itself.
- `deepfellow suite install --resume` no longer crashes with an unhandled traceback if the persisted `workspace` data in the state file is corrupted or has an unexpected shape - it now fails with a clear message telling the user to remove the state file and start fresh, the same as any other step failure. This now also covers a corrupted `api_key` field specifically, which previously raised `AttributeError` instead of the `TypeError`/`KeyError` the original fix caught.
- `deepfellow suite install`'s state file is now written atomically (temp file + rename) instead of being truncated in place, so a crash mid-write (OOM kill, Ctrl+C, power loss) can no longer leave a corrupted file behind that silently loses whatever progress - including a one-time, unrecoverable workspace API key - it was holding.
- `deepfellow suite install --resume` no longer crashes with an unhandled traceback when the state file's `completed_steps` field is present but explicitly `null` (as opposed to being absent) - it's now treated the same as a missing field, defaulting to an empty list.
- `deepfellow suite install --resume` no longer re-prompts for the admin name/email/password on every re-run — the credentials resolved by the first run are now written to the state file immediately, before any step even runs (not lazily on the first step's own success), and reused on `--resume`, while an explicit `--admin-name`/`--admin-email`/`--admin-password` (or `DF_SERVER_ADMIN_*` env var) on the resuming invocation still overrides the persisted value. Without the immediate write, a step that never succeeds (e.g. the user repeatedly declining infra install's own directory-exists confirmation) meant nothing was ever saved, forcing the same name/email/password to be retyped on every single retry.
- `deepfellow suite install` now warns when an admin name/email/password just supplied on this invocation — via an explicit `--admin-name`/`--admin-email`/`--admin-password` flag, or by being typed at the interactive prompt — is silently ignored because an admin for that email already exists; `create_admin` can only create or no-op, it can't rename/reset an existing account. Previously only the flag case was covered: typing a different password than what's actually live on the server (e.g. after a plain re-run reset the persisted state) produced no warning at all, just a confusing, unrelated authentication error two steps later at login.
- `deepfellow server create-admin` (the standalone command) now fails with an error again when an admin for the given email already exists, instead of silently exiting successfully — a side effect of making `create_admin` idempotent for `suite install --resume`/`server install --template` reinstalls, which don't apply to this direct, explicit command: a user invoking it is asking to create an admin right now, so an existing account is this command's own failure to report. It no longer also prints the shared "already exists; skipping" info message right before its own error — the two read as one message implying success immediately followed by a contradictory one implying failure; `suite install`'s and `server install --template`'s own reinstall flows still get that info message as before.
- `deepfellow suite install --debug` now shows the specific Docker error when infra or server start fails (e.g. a network conflict, a Mongo credential mismatch), instead of a generic "Installation failed; see console output above for details." — matching `infra install`'s/`server install`'s own `--debug` behavior for the same failure. (The initial fix only covered server start; infra start was left on the old, generic-message behavior.)
- `infra service list`, `infra service uninstall`, and `infra model uninstall` no longer save a resolved server URL or admin API key to the local config/secrets files until a request made with them has actually succeeded — a wrong `--url` or a rejected API key can no longer overwrite a previously working, saved configuration.
- `deepfellow suite install` now warns when its state file exists but can't be read or parsed (e.g. corrupted by a crash mid-write), instead of silently treating it as "nothing to resume" — this could otherwise make an explicit `--resume` quietly start fresh with no indication anything was wrong.
- `server install --template`/`infra install --template` no longer re-prompt (or, worse, silently fall back to the CLI's own hardcoded default) for a field that's already configured by a prior install's `.env`/`config.json` and merely blocked from being overwritten by the template — e.g. re-running `deepfellow suite install --resume` on step 7 (server install) after an earlier partial attempt used to interactively re-ask for the docker network name, Infra URL, vector DB URL/type, and embedding model/size, one prompt after another, even though every one of them was already resolved.
- `deepfellow infra service install` / `deepfellow infra model install` (and therefore `deepfellow suite install`, which drives both internally) no longer abort with "... already installing" when a previous, interrupted attempt (e.g. Ctrl+C during an ollama model download) left an install running server-side. The CLI now waits and retries every 10s, for up to 24h, instead of failing immediately — matching how "... already installed" is already treated as a no-op.
- `deepfellow suite install` now looks up the port `server install` actually resolved (from the server's own `.env`) before logging in and creating the workspace, instead of assuming the raw `--server-port` value — a re-run against an existing server directory with a different already-configured port previously failed at the login step.
- `create_admin` (used by `server install`'s post-install action and `suite install`) now treats an admin that already exists for the given email as a successful no-op instead of aborting — needed for `suite install --resume` to safely re-enter the create-admin step, and also makes a `server install --template` reinstall idempotent for this step, consistent with `infra service install`'s existing "already installed" no-op.

## [0.32.0] - 2026-09-01
### Added
- `infra mcp add <name>`, `infra mcp install <name>`, `infra mcp list`, `infra mcp uninstall <name>`, and `infra mcp remove <name>` — register, install, list, uninstall, and remove MCP servers on DeepFellow Infra's built-in `mcp` service. `add` reads a standard MCP client config JSON (`--config <file>` or stdin) and forwards it to Infra's `/admin/mcp/convert-config` and custom-model endpoints, but only registers the server's configuration — it does not start it. `install` starts a model (a built-in one from Infra's catalog, e.g. `brave-search`, or one already registered via `add`), prompting for any field its install-form schema marks as required (e.g. an API key) via `--set`/`--api-key`/interactive prompt, the same way the WebUI's install form does; this logic is shared with `infra service install` via the new `deepfellow/infra/utils/fields.py`. `list` shows each entry's `description` and, while it's not yet installed, every field from its install-form schema (`fields:`, e.g. `brave-search` needing a `BRAVE_API_KEY`) so the user can see what a built-in model requires before attempting to install it. The CLI does no local parsing or Docker provisioning, since Infra already handles config parsing, runtime bridging, and container provisioning. `uninstall` stops a running instance (built-in or custom) and takes a `--purge` flag, consistent with `infra service uninstall`/`infra model uninstall`, to also remove the server's files. `remove` deletes a custom model's registration from the models list entirely (built-in models can't be removed this way — use `uninstall --purge` instead). DeepFellow Server has no equivalent command: it has no server-wide MCP registry, only per-toolbox tools (`mcp`/`infra-mcp`/`custom-mcp`) that reference a raw URL or an Infra-provisioned prefix.
- `infra service install`/`infra mcp install` now offer a pick-list of the actual tags available on the image's Docker registry for a `docker-tags` field (e.g. an MCP server's `image_version`), via the new `deepfellow.common.registry.list_image_tags()`, instead of asking the user to type a version blind. Falls back to the previous free-text prompt if the registry can't be reached or reports no tags.
- `deepfellow suite install` gains a `--force-install` flag, forwarded to both its `infra install` and `server install` steps, so a scripted/non-interactive suite install can force a reinstall over an already-existing `~/.deepfellow/infra` or `~/.deepfellow/server` directory without manually removing it first.
- `deepfellow server install` and `deepfellow suite install` now accept the admin user's name/email/password via `DF_SERVER_ADMIN_NAME`/`DF_SERVER_ADMIN_EMAIL`/`DF_SERVER_ADMIN_PASSWORD` environment variables, in addition to the existing `--admin-name`/`--admin-email`/`--admin-password` flags — so a scripted or CI install no longer has to put the password on the command line, where it would leak into shell history and process listings.
- `deepfellow suite install` now checks Docker availability before prompting for admin credentials, instead of only checking once step 1 (infra install) runs — so a missing/unusable Docker installation is caught immediately instead of after the admin name/email/password prompts.
- `deepfellow server project update` — update an existing project's `name`, `models`, `custom_endpoints`, or `mcp_prefixes` without archiving and recreating it. `--models`/`--custom-endpoints`/`--mcp-prefixes` add to the project's existing list by default; pass `--overwrite` to replace the list with exactly what's given instead. `status` isn't exposed: the server's project-update endpoint silently ignores it (confirmed against the server source — its update model has no `status` field), so archiving stays exclusively the job of the existing `server project archive` command.
- `deepfellow suite install` gains flags for infra/server configuration that previously required falling back to separate `infra install`/`server install` runs: disambiguated `--infra-port`/`--server-port`, `--infra-image`/`--server-image`, `--infra-local-image`/`--server-local-image`, and `--infra-directory`/`--server-directory`, a shared `--docker-network`, infra's `--infra-docker-config`/`--infra-storage`, and server's `--mongodb-port`/`--mongodb-username`/`--mongodb-password`, `--falkordb-active`/`--falkordb-url`/`--falkordb-username`/`--falkordb-password`, and `--otel-local`. Options already reachable through `suite install`'s existing interactive prompts (VectorDB, embedding, Mongo URL/database name, OTel URL, Hugging Face/Civitai tokens, `--template`) are deliberately not exposed as flags.

### Changed
- `deepfellow suite install` now reuses the built-in `workspace` templates that `infra install`/`server install` already expose via `--template`, instead of hardcoding its own copy of the same defaults (ollama service spec, chat/embedding/fast model names, Milvus config). No change in behavior or output for the end user.
- `deepfellow server install`'s Knowledge Graph feature is now backed by FalkorDB instead of Neo4j, matching what the DeepFellow Server actually runs: `--neo4j-active`/`--neo4j-url`/`--neo4j-username`/`--neo4j-password` are replaced by `--falkordb-active`/`--falkordb-url`/`--falkordb-username`/`--falkordb-password`, and the generated `.env` now writes `DF_GRAPH__{ENABLED,HOST,PORT,USERNAME,PASSWORD}` instead of `DF_GRAPHITI__{ENABLED,NEO4J_URI,NEO4J_USER,NEO4J_PASSWORD}` (the old Neo4j wiring never matched what the Server read).

### Fixed
- `infra mcp list` no longer shows every model's `installed` status as `True` regardless of its real state, and no longer dumps a model's install-form field schema (`spec.fields` — the same shape for every model of a kind, whether or not it's installed) under `parameters:` as if it were a server's actual configuration. `installed` now reflects the backend's own boolean field, and `parameters:` shows a custom model's real `custom_spec` (`command`/`args`/`envs`/etc.) instead. It also no longer re-persists and re-prints "Updated config"/"Updated secrets" on every run of this read-only command.
- `install_with_progress` (used by `infra service install`, `infra model install`, and the new `infra mcp install`) no longer crashes with `httpx.ResponseNotRead` when the backend rejects an install with a status code other than 400/401/403 (e.g. 422) — the response body is now read for any error status while still inside the streaming context, so `call_infra` can extract and display the backend's actual error message instead.
- `infra mcp add <name>` now checks upfront whether `<name>` is already taken (by a built-in model or one added before) and reports it immediately, before asking for/reading a config — previously the check only happened at the very end, after the user had already supplied a config and, for a Docker-image config, answered `--prefix`/`--image-port` prompts, for a request that was always going to fail.
- A field's `description` (in `infra service fields`/`infra mcp list`/an install prompt) no longer breaks its rendering onto a stray unindented line when the backend embeds a literal newline in it (e.g. an `envs` field's "Custom enviromental variables.\nRequired variables: BRAVE_API_KEY") — embedded whitespace is now collapsed onto one line before display.
- `deepfellow infra service install` and `deepfellow infra model install` now show an activity indicator during the install phase (spinner interactively, a periodic `install: still working… (Ns)` line in `--non-interactive` mode) instead of jumping from `install: 0%` to `install: 100%` after a long silence.
- `deepfellow server install` no longer aborts with "Invalid DF_PLUGINS_SETUP" when reinstalling over a server that has actually been started at least once. Unlike every other setting, `DF_PLUGINS_SETUP` is stored in `.env` as one raw JSON-string blob rather than decomposed into `DF_X__Y__Z` keys, but the Server's own `config.json` (merged in on top of `.env` once a prior install is confirmed) stores it as a real JSON object — the merge was leaving that object in place instead of a string, tripping a type check even though the content itself was always valid JSON. `merge_config_json_into_env()`'s underlying deep-merge now detects this shape (a `.env`-side string with a `config.json`-side object for the same key) structurally and re-serializes the object back to a string, rather than special-casing this one field's name.
- `deepfellow server install --directory` now warns when a fresh install at a new directory would actually share its storage (config.json, uploads) with an install already sitting elsewhere on the machine, and its `--help` text now says storage is shared globally across every install on the machine and can't be relocated per `--directory` (unlike `infra install`, which exposes a `--storage` option for this).
- `deepfellow infra install --template` no longer lets a template's value silently override an explicit CLI flag when the flag happens to equal its own default (e.g. an explicit `--port 8000` matching `port`'s own default) - the explicit flag now always wins, as documented.
- `deepfellow infra install` now correctly restores a prior install's port from `.env` on a plain re-run with no `--template`, or with a template that doesn't declare a port, instead of silently resetting it to the hardcoded default.
- `deepfellow infra uninstall` now asks interactively whether to also remove Docker images (when `--remove-images`/`--no-remove-images` isn't passed), instead of removing the directory first and only afterward suggesting a `--remove-images` follow-up that could never work (the directory it depends on was already gone). Running `--remove-images` after the directory is already gone now reports a clear "already uninstalled" message instead of the misleading "Create Deepfellow Infra first."
- `server install --template` and `infra install --template` now also check `config.json` (best-effort, in addition to `.env`) before applying a template value, so a `--template` reinstall no longer silently overwrites a setting that migrated to `config.json` after the service's first start.
- `deepfellow suite install` now grants the workspace's project access to the three models (chat, embedding, fast) it just installed, via a follow-up call to the server's project-update endpoint right after workspace creation — previously the created project had no model access at all, contradicting the command's "ready-to-use workspace" promise.
- `deepfellow infra service install` and `deepfellow infra model install` now show the real failure reason on install error: both were reading the wrong SSE finish-event key (`detail`/`error`) instead of the `details` key the Infra Server actually sends, so a populated error message was silently dropped in favor of a fully generic failure message. When the server sends no details at all, the CLI now also points the user at `docker compose logs infra`.
- `deepfellow infra service install` no longer aborts when the target service is already installed on the Infra instance — the Infra API's `{"error": {"message": "... already installed"}}` response is now parsed into a readable message (previously fell back to printing the raw JSON body) and treated as a no-op, printing an informational message and exiting successfully instead of failing. This also makes `infra install --template`'s `post_start_actions` idempotent: a step targeting an already-installed service is skipped instead of aborting the whole install after 0 of N actions complete. (`infra model install` already reports success for a duplicate model in every case — Infra itself never returns an error for it.)
- CLI no longer crashes with a raw `KeyError` traceback instead of a readable error message when the DeepFellow Server reports an error in its newer `{"error": {"message": ...}}` format.
- `deepfellow infra install`/`server install` in `--non-interactive` mode now explains how to proceed (pass `--force-install` or remove the directory manually) when the target directory already exists, instead of aborting with no guidance.
- `deepfellow suite install --non-interactive` now reports every missing admin value (name, email, password) in a single error naming the exact `--admin-name`/`--admin-email`/`--admin-password` flags to pass, instead of aborting on just the first missing value with a message that didn't name a flag.
- The test suite no longer writes to the real `~/.deepfellow/config` and `~/.deepfellow/secrets` — an autouse fixture now points the CLI config/secrets paths (and their `DF_CLI_CONFIG_PATH`/`DF_CLI_SECRETS_PATH` env vars) at `tmp_path` for every test. Previously `just test` replaced the developer's Infra URL with `http://infra:8086` and their admin API key with `test-key`, so the next `deepfellow infra ...` call failed with "No connection with DeepFellow Infra" or "Unauthorized".
- `test_dynamic_field_name_returns_none_when_no_user_token_stored` no longer reads the real `~/.deepfellow/secrets` on the machine running the tests — it previously passed only by coincidence when that file had no `DF_USER_TOKEN`, and failed once one was actually present (e.g. after a real `deepfellow server login`).

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
