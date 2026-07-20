## ADDED Requirements

### Requirement: install() accepts pre-answered confirm decisions
`deepfellow.infra.utils.install.install()` SHALL accept four optional parameters — `allow_print_keys: bool | None = None`, `keep_compose_prefix: bool | None = None`, `keep_storage: bool | None = None`, `keep_metrics: bool | None = None` — and SHALL pass each as the `from_args` argument to its corresponding `echo.confirm()` call, replacing the previously unconditional prompt for that decision.

#### Scenario: All four params supplied produces zero confirm prompts
- **WHEN** `install()` is called with `allow_print_keys`, `keep_compose_prefix`, `keep_storage`, and `keep_metrics` all set to explicit `bool` values, and a previous installation exists with a compose prefix, storage dir, and metrics credentials already configured
- **THEN** none of the 4 confirm-driven decisions SHALL prompt the user, and each SHALL resolve to the supplied value

#### Scenario: Omitted params preserve current prompting behavior
- **WHEN** `install()` is called without `allow_print_keys`, `keep_compose_prefix`, `keep_storage`, or `keep_metrics` (all `None`)
- **THEN** each decision SHALL behave exactly as before this change — prompting interactively, or falling back to its existing default in non-interactive mode

### Requirement: Keep-previous guards are unaffected by from_args
Supplying `keep_compose_prefix`, `keep_storage`, or `keep_metrics` SHALL NOT bypass the existing guard that a previous value must exist before the "keep previous" decision is meaningful. If no previous value exists, `install()` SHALL proceed as it does today (generating a fresh value) regardless of the supplied parameter.

#### Scenario: keep_compose_prefix=True has no effect when there is no previous prefix
- **WHEN** `install()` is called with `keep_compose_prefix=True` and no `df_infra_compose_prefix` exists in the target directory's `.env`
- **THEN** `install()` SHALL generate a new random compose prefix, as it does today, without consulting `keep_compose_prefix`

### Requirement: infra install CLI exposes the four confirm decisions as tri-state flags
The `infra install` Typer command SHALL expose `--allow-print-keys/--no-allow-print-keys`, `--keep-compose-prefix/--no-keep-compose-prefix`, `--keep-storage/--no-keep-storage`, and `--keep-metrics/--no-keep-metrics` options, each defaulting to `None` (not passed), and SHALL forward each to `install()`'s matching parameter.

#### Scenario: Flag passed on the command line skips its prompt
- **WHEN** `df infra install --allow-print-keys` is run
- **THEN** `install()` SHALL be invoked with `allow_print_keys=True` and SHALL NOT prompt "Is it safe to print API keys here?"

#### Scenario: Flag omitted preserves current CLI behavior
- **WHEN** `df infra install` is run without any of the four new flags
- **THEN** `install()` SHALL be invoked with all four new parameters as `None`, and behavior SHALL be identical to before this change
