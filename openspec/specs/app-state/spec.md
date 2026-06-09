## ADDED Requirements

### Requirement: AppState singleton holds CLI runtime flags
The system SHALL expose a module-level `state` singleton of type `AppState` at `deepfellow.common.state`. It SHALL carry the following fields with the specified defaults: `debug: bool = False`, `yes: bool = False`, `non_interactive: bool = False`, `cli_config: dict[str, Any] = {}`, `cli_config_file: Path = DF_CLI_CONFIG_PATH`, `cli_secrets_file: Path = DF_CLI_SECRETS_PATH`. The two path fields are non-optional because `main()` always populates them before any subcommand runs.

`AppState` SHALL be a true singleton: constructing `AppState()` anywhere SHALL return the one shared instance (the same object as `state`), never a second divergent copy. It SHALL expose a `reset()` method that restores every field to its default, used for test isolation.

#### Scenario: Default state before main() runs
- **WHEN** any module imports `state` before `main()` has executed
- **THEN** all fields SHALL have their default values (debug=False, non_interactive=False, etc.)

#### Scenario: Repeated construction returns the same instance
- **WHEN** any code calls `AppState()` after `state` already exists
- **THEN** it SHALL receive the existing `state` instance and SHALL NOT reset its current field values

#### Scenario: State populated by main() callback
- **WHEN** the `main()` Typer callback executes with `--debug`, `--yes`, `--non-interactive`, `--config`, `--secrets` flags
- **THEN** `state.debug`, `state.yes`, `state.non_interactive`, `state.cli_config_file`, `state.cli_config`, and `state.cli_secrets_file` SHALL reflect those values for the lifetime of the command

### Requirement: is_interactive() reads from AppState
The `is_interactive()` function in `deepfellow.common.echo` SHALL return `not state.non_interactive` without calling `click.get_current_context()`.

#### Scenario: Interactive mode (default)
- **WHEN** `state.non_interactive` is `False`
- **THEN** `is_interactive()` SHALL return `True`

#### Scenario: Non-interactive mode
- **WHEN** `state.non_interactive` is `True`
- **THEN** `is_interactive()` SHALL return `False`

### Requirement: Echo.debug() reads from AppState
`Echo.debug()` SHALL print only when `state.debug` is `True`, without calling `click.get_current_context()`.

#### Scenario: Debug output suppressed
- **WHEN** `state.debug` is `False`
- **THEN** `Echo.debug()` SHALL produce no output

#### Scenario: Debug output shown
- **WHEN** `state.debug` is `True`
- **THEN** `Echo.debug()` SHALL print the message

### Requirement: reraise_if_debug() reads from AppState
`reraise_if_debug()` in `deepfellow.common.exceptions` SHALL re-raise the exception when `state.debug` is `True`, without calling `click.get_current_context()`.

#### Scenario: Debug off — exit instead of reraise
- **WHEN** `state.debug` is `False` and `reraise_if_debug(exc)` is called
- **THEN** the function SHALL raise `typer.Exit(1)` rather than re-raising the original exception

#### Scenario: Debug on — original exception propagates
- **WHEN** `state.debug` is `True` and `reraise_if_debug(exc)` is called inside an except block
- **THEN** the original exception SHALL propagate

### Requirement: get_server_url() reads from AppState
`get_server_url()` in `deepfellow.common.rest` SHALL read `cli_config_file` and `cli_config` from `state` without calling `click.get_current_context()`.

#### Scenario: Config server URL used when present
- **WHEN** `state.cli_config` contains a `df_server_url` key and `server` argument is `None`
- **THEN** `get_server_url()` SHALL use that URL without prompting

#### Scenario: User prompted when no config URL
- **WHEN** `state.cli_config` does not contain `df_server_url` and `server` argument is `None`
- **THEN** `get_server_url()` SHALL prompt the user for a server address

### Requirement: Subcommands read CLI flags from AppState
Final subcommands SHALL read CLI-wide flags (`cli_config_file`, `cli_config`, `cli_secrets_file`, `yes`) from the `state` singleton and SHALL NOT accept a `ctx: typer.Context` parameter for the purpose of reading those flags. Helpers in `deepfellow.server.utils.options` SHALL likewise read from `state`.

#### Scenario: Subcommand reads secrets file from state
- **WHEN** a subcommand such as `server logout` needs the CLI secrets file path
- **THEN** it SHALL read `state.cli_secrets_file` rather than `click.get_current_context().obj`

### Requirement: No direct click dependency
The `deepfellow` package SHALL NOT declare `click` as a direct dependency in `pyproject.toml`. Typer's vendored click SHALL be the sole click provider.

#### Scenario: Installation without explicit click
- **WHEN** `pip install deepfellow-cli` is run with the latest compatible Typer
- **THEN** the package SHALL install and all CLI commands SHALL function without a separate `click` package being required

### Requirement: Typer pinned to 0.26.x
The `typer` dependency in `pyproject.toml` SHALL be specified as `typer~=0.26.0`.

#### Scenario: Install with Typer 0.26.x
- **WHEN** the package is installed
- **THEN** Typer 0.26.x SHALL resolve and all CLI commands SHALL execute without `RuntimeError: There is no active click context`
