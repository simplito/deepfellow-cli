## ADDED Requirements

### Requirement: List MCP servers provisioned on DeepFellow Infra
The CLI SHALL provide an `infra mcp list` command that fetches the models of Infra's built-in `mcp` service via `GET /admin/services/mcp/models` and display each entry's name/id, kind, and installed status (taken directly from the entry's own boolean `installed` field), plus its `description` when the backend reports one. A custom model's launch parameters (`command`/`args`/`envs`/`server_url`, etc.) are carried in its `custom_spec` field; when present, that `custom_spec` SHALL be shown under a `parameters:` line below the `installed:` status line, rather than the status value itself, so it reads as the server's run configuration rather than as part of the status. Any credential-bearing fields `custom_spec` carries (`envs`, `headers`, `oauth`) SHALL have their values redacted (shown as `*****`) before being printed, for the same reason as in `mcp add` (see mcp-server-add). The backend's internal `custom_model_id` SHALL NOT be printed unless the CLI is running in debug mode, since no command requires the user to supply it (servers are always referenced by name). This command SHALL NOT re-persist and re-announce the resolved Infra connection ("Updated config"/"Updated secrets") on every run — it is read-only and, once the connection is already known to work, has nothing new to confirm.

For an entry that is not yet installed, its `spec.fields` (the same install-form field schema `mcp install` resolves a spec from — see mcp-server-install) SHALL be shown under a `fields:` line, one bullet per field with its name, description, and default, so the user can see what a built-in model like `brave-search` would need (e.g. a `BRAVE_API_KEY`) without first attempting `mcp install` and hitting an error, or checking the WebUI. All fields SHALL be shown, not only ones the schema marks `required: true`: a field can be schema-optional while its `description` still names a required sub-value (e.g. `brave-search`'s `envs` field is schema-optional but its description reads "Required variables: BRAVE_API_KEY"), so filtering on the `required` flag alone would hide it. `fields:` SHALL NOT be shown once a model is installed, since by then either `parameters:` already shows its real configuration (a custom model) or the install-form no longer describes anything actionable (a built-in one).

#### Scenario: Listing with provisioned servers
- **WHEN** the user runs `infra mcp list` and the `mcp` service has one or more custom models provisioned
- **THEN** the CLI prints each MCP server's id, kind, and status, and a custom model's launch parameters under `parameters:` when the backend reports a `custom_spec`

#### Scenario: Listing with no provisioned servers
- **WHEN** the user runs `infra mcp list` and the `mcp` service has no custom models
- **THEN** the CLI prints an informational message that no MCP servers are provisioned, and exits with status 0

#### Scenario: custom_model_id is hidden outside debug mode
- **WHEN** the user runs `infra mcp list` without `--debug`/`-v`
- **THEN** the CLI does not print the `custom_model_id` field for any entry

#### Scenario: custom_model_id is shown in debug mode
- **WHEN** the user runs `infra mcp list --debug`
- **THEN** the CLI prints each entry's `custom_model_id`, e.g. for correlating with Infra's own logs

#### Scenario: An uninstalled model shows its description and install-form fields
- **WHEN** the user runs `infra mcp list` and the `brave-search` built-in model is not installed
- **THEN** the CLI prints its `description` and, under `fields:`, every field from its `spec.fields` schema (including `envs`, whose description names `BRAVE_API_KEY` as required, even though the field itself isn't schema-required)

#### Scenario: An installed model does not repeat its install-form fields
- **WHEN** the user runs `infra mcp list` and an entry's `installed` is `true`
- **THEN** the CLI does not print a `fields:` line for that entry
