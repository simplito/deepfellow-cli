## ADDED Requirements

### Requirement: Uninstall (stop) an MCP model instance by name
The CLI SHALL provide an `infra mcp uninstall <name>` command that stops a running instance of any model on Infra's built-in `mcp` service by id — either a built-in model from Infra's catalog (e.g. `duckduckgo`) or a custom model registered via `infra mcp add` — via `DELETE /admin/services/mcp/models/_?model_id=<name>`, forwarding a `--purge` flag (default `false`) as `{"purge": <bool>}` in the request body, mirroring `infra model uninstall`. Unlike `infra mcp remove`, this does not touch a custom model's registration in the models list — it only stops/removes the running instance, so it works for built-in models too.

#### Scenario: Uninstall an existing MCP server instance
- **WHEN** the user runs `infra mcp uninstall my-server` and a model named `my-server` (built-in or custom) exists on the `mcp` service
- **THEN** the CLI calls the delete endpoint with `{"purge": false}`, and confirms the uninstall to the user

#### Scenario: Uninstall and purge an existing MCP server instance
- **WHEN** the user runs `infra mcp uninstall my-server --purge` and a model named `my-server` exists on the `mcp` service
- **THEN** the CLI calls the delete endpoint with `{"purge": true}`, and confirms the uninstall to the user

#### Scenario: Uninstall a built-in MCP model
- **WHEN** the user runs `infra mcp uninstall duckduckgo` where `duckduckgo` is a built-in MCP model with no `custom_model_id`
- **THEN** the CLI stops it the same way as a custom model, since uninstall only affects the running instance, not any registration

#### Scenario: Backend reports failure
- **WHEN** the delete endpoint responds with a status other than `"ok"`
- **THEN** the CLI reports that the MCP server could not be uninstalled and exits with a non-zero status
