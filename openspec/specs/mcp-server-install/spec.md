## ADDED Requirements

### Requirement: Install (start) an MCP model by name
The CLI SHALL provide an `infra mcp install <name>` command that installs a model of Infra's built-in `mcp` service by id — either a built-in model from Infra's catalog (e.g. `brave-search`) or a custom model already registered via `infra mcp add`. It resolves the model's install-form field schema (its `spec.fields`, as also fetched by `infra mcp list`) via `GET /admin/services/mcp/models`, builds a spec from `--set`/`--api-key`/interactive prompts for fields the schema marks required (falling back to each field's default), and installs it via `POST /admin/services/mcp/models/_?model_id=<name>` with `{"spec": <resolved spec>}`, mirroring `infra service install`'s field-resolution behavior. A custom model added via `mcp add` typically needs no field values here, since its configuration was already baked into its spec at `add` time — but installing it is still required to actually start it, since `add` only registers it (see mcp-server-add).

#### Scenario: Install a built-in model prompts for a required field
- **WHEN** the user runs `infra mcp install brave-search` and the `brave-search` model's field schema marks its `envs` field as needing `BRAVE_API_KEY`, with no `--set`/`--spec` given
- **THEN** the CLI prompts for the field interactively before installing, unless running non-interactively with no default, in which case it reports the missing required field and exits with a non-zero status

#### Scenario: Fields can be supplied without prompting
- **WHEN** the user runs `infra mcp install brave-search --set envs='{"BRAVE_API_KEY": "..."}'` or `--spec '{"envs": {"BRAVE_API_KEY": "..."}}'`
- **THEN** the CLI uses the given value(s) instead of prompting, and (for `--spec`) skips fetching the model's field schema entirely

#### Scenario: Install a custom model registered via add
- **WHEN** the user runs `infra mcp install my-server` for a model previously registered via `infra mcp add my-server`
- **THEN** the CLI installs it (typically with an empty resolved spec, since its configuration is already part of its custom spec) and the model's `installed` status becomes `true`

#### Scenario: Install a name that does not exist
- **WHEN** the user runs `infra mcp install unknown-server` and no model with that id exists on the `mcp` service
- **THEN** the CLI reports that the MCP server was not found and exits with a non-zero status, without attempting to install

#### Scenario: Already-installed model is skipped, not treated as an error
- **WHEN** the user runs `infra mcp install <name>` for a model that is already installed
- **THEN** the CLI reports that it is already installed and exits with status 0, rather than treating the backend's rejection as a failure
