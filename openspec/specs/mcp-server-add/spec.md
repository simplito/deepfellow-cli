## ADDED Requirements

### Requirement: Convert and register an MCP server from a standard config JSON
The CLI SHALL provide an `infra mcp add <name>` command that reads a standard MCP client config JSON (the `mcpServers` wrapper or a bare server object), sends it to DeepFellow Infra's `/admin/mcp/convert-config` endpoint to obtain a normalized spec, and registers that spec as a custom model on Infra's built-in `mcp` service via `/admin/services/mcp/models/custom`. Both `id` and `name` in the spec SHALL be overwritten with the given `<name>` before registering, so that `mcp list`/`mcp install`/`mcp uninstall` — which match a server by `id` — can find it under the name the user chose. This only registers the server's configuration; it does not start it (see mcp-server-install) — the model's `installed` status remains `false` until `infra mcp install <name>` is run.

#### Scenario: Add an MCP server from a file
- **WHEN** the user runs `infra mcp add my-server --config ./config.json` where `config.json` contains a valid `{"mcpServers": {...}}` document
- **THEN** the CLI resolves the DeepFellow Infra connection, reads the file, posts its contents to `/admin/mcp/convert-config`, posts the returned spec (with `id` and `name` set to `my-server`) to `/admin/services/mcp/models/custom`, and tells the user to run `infra mcp install my-server` to start it (showing the resulting custom model id only in debug mode, since no command requires the user to supply it)

#### Scenario: Add an MCP server from stdin
- **WHEN** the user runs `infra mcp add my-server` without `--config` and pipes a valid MCP config JSON on stdin
- **THEN** the CLI reads the JSON from stdin and follows the same convert-then-provision flow as when `--config` is given, except that if the converted spec's `kind` is `custom` (see below) it requires `--prefix` and `--image-port` to already be provided rather than prompting

#### Scenario: Invalid or unsupported MCP config
- **WHEN** Infra's `/admin/mcp/convert-config` endpoint responds with an error (e.g. malformed JSON or an unsupported `command`)
- **THEN** the CLI prints the backend's error message via `echo.error` and exits with a non-zero status, without calling the custom-model provisioning endpoint

### Requirement: Collect prefix and image port for Docker-image-based configs
When the converted spec's `kind` is `custom` (a Docker-image-based MCP server, e.g. converted from a `docker run` command), the backend cannot infer an endpoint prefix or the image's listening port from the spec alone. The CLI SHALL collect both via `--prefix`/`--image-port` or, when standard input is a TTY, by prompting for any that are missing before provisioning. The image port SHALL be validated as a number between 1 and 65535, re-prompting on invalid input in interactive mode.

#### Scenario: Prefix and image port are prompted for interactively
- **WHEN** the user runs `infra mcp add my-server --config ./docker-config.json` with a config that converts to `kind: custom`, without `--prefix`/`--image-port`, and standard input is a TTY
- **THEN** the CLI prompts for the endpoint prefix and the Docker image port (re-prompting on an invalid port) before provisioning the custom model

#### Scenario: Prefix or image port missing with no TTY available
- **WHEN** the config converts to `kind: custom`, `--prefix` or `--image-port` was not given, and standard input is not a TTY (e.g. it was used to pipe the config, or is redirected/closed as in a CI job)
- **THEN** the CLI prints an error via `echo.error` and exits with a non-zero status, without attempting to prompt (which would fail with `EOFError` on an unusable stream)

### Requirement: Show the converted spec before provisioning
The CLI SHALL print the spec returned by `/admin/mcp/convert-config` (`kind` and every backend-specific field: `command`/`envs`/`variant`, or `server_url`/`transport`/`headers`/`oauth`, or `image`/`command`/`volumes`/`envs`) to the user before provisioning it, so the user can see how their config was actually interpreted (e.g. detected runtime variant, or the image/volumes parsed out of a `docker run` command) rather than only learning the outcome from a later `mcp list`. Credential-bearing fields (`envs`, `headers`, `oauth`) SHALL have their values redacted (shown as `*****`) in this output, since they routinely carry secrets (e.g. API tokens, `Authorization` headers) that must not be printed in plaintext; the unredacted spec is still what gets provisioned.

#### Scenario: Converted spec is shown before provisioning
- **WHEN** the user runs `infra mcp add my-server --config ./config.json`
- **THEN** the CLI prints the converted spec's fields (as returned by `/admin/mcp/convert-config`, before `id`/`name` are overwritten) via `echo.info`, then proceeds to provision it as before

#### Scenario: Credentials are redacted when the spec is printed
- **WHEN** the converted spec includes `envs`, `headers`, or `oauth` fields containing secret values
- **THEN** the CLI prints those fields with their values replaced by `*****` (dict values masked per-key, scalar values masked wholesale), while still provisioning the unredacted spec to `/admin/services/mcp/models/custom`

#### Scenario: Credential-looking tokens embedded in other fields are also masked
- **WHEN** a field outside `envs`/`headers`/`oauth` (e.g. `command`, `args`, `server_url`) contains a string with a credential-looking `key=value` token, such as a Docker `-e GITHUB_TOKEN=ghp_xxx` argument or a URL query string carrying `?token=...`
- **THEN** the CLI masks the value portion of that token before printing, while still provisioning the unredacted spec

### Requirement: No local Docker or MCP-bridge logic
The CLI SHALL NOT run Docker commands, select a stdio↔HTTP bridge (e.g. `supergateway`, `mcp-proxy`), or maintain a local registry file when adding an MCP server; all such logic is performed by DeepFellow Infra.

#### Scenario: Add succeeds without a local Docker daemon
- **WHEN** the user runs `infra mcp add` on a machine with no Docker installed or running locally
- **THEN** the command succeeds as long as DeepFellow Infra is reachable and provisions the model successfully
