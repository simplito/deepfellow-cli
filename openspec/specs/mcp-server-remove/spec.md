## ADDED Requirements

### Requirement: Remove a provisioned MCP server's registration by name
The CLI SHALL provide an `infra mcp remove <name>` command that resolves `<name>` to a `custom_model_id` by listing Infra's `mcp` service's models, then removes its registration via `DELETE /admin/services/mcp/models/custom/{custom_model_id}`. This only deletes a custom model's registration from the models list — use `infra mcp uninstall` to stop a running instance (built-in or custom) without deleting anything.

#### Scenario: Remove an existing custom MCP server
- **WHEN** the user runs `infra mcp remove my-server` and a custom model named `my-server` exists on the `mcp` service
- **THEN** the CLI resolves its custom model id, calls the delete endpoint, and confirms removal to the user

#### Scenario: Remove a name that does not exist
- **WHEN** the user runs `infra mcp remove unknown-server` and no model with that name exists on the `mcp` service
- **THEN** the CLI reports that the MCP server was not found and exits with a non-zero status, without calling the delete endpoint

#### Scenario: Remove a built-in (non-custom) MCP model
- **WHEN** the user runs `infra mcp remove <name>` where `<name>` matches a built-in MCP model that has no `custom_model_id`
- **THEN** the CLI reports that the model is a built-in model and cannot be removed, points the user at `infra mcp uninstall <name> --purge` instead, and exits with a non-zero status
