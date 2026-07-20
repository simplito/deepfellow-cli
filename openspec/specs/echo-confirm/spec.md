## ADDED Requirements

### Requirement: Echo.confirm() accepts a from_args override
`Echo.confirm()` SHALL accept an optional `from_args: bool | None = None` parameter. When `from_args` is not `None`, `confirm()` SHALL return it immediately without prompting, in both interactive and non-interactive mode, and SHALL log an info message noting the value was set automatically.

#### Scenario: Explicit True skips the prompt in interactive mode
- **WHEN** `confirm("Keep X?", from_args=True)` is called and `state.non_interactive` is `False`
- **THEN** the function SHALL return `True` without calling `Confirm.ask`

#### Scenario: Explicit False skips the prompt in interactive mode
- **WHEN** `confirm("Keep X?", from_args=False)` is called and `state.non_interactive` is `False`
- **THEN** the function SHALL return `False` without calling `Confirm.ask`

#### Scenario: Explicit value used in non-interactive mode
- **WHEN** `confirm("Keep X?", from_args=True)` is called and `state.non_interactive` is `True`
- **THEN** the function SHALL return `True` without consulting `kwargs["default"]`

### Requirement: Echo.confirm() preserves current behavior when from_args is None
When `from_args` is `None` (the default), `Echo.confirm()` SHALL behave exactly as before this change: non-interactive mode returns `kwargs["default"]` (or `False` if no default was supplied) without prompting, and interactive mode prompts via `Confirm.ask`.

#### Scenario: Non-interactive mode without from_args falls back to default silently
- **WHEN** `confirm("Keep X?", default=True)` is called with `from_args` omitted and `state.non_interactive` is `True`
- **THEN** the function SHALL return `True` without prompting and without raising

#### Scenario: Interactive mode without from_args still prompts
- **WHEN** `confirm("Keep X?")` is called with `from_args` omitted and `state.non_interactive` is `False`
- **THEN** the function SHALL prompt the user via `Confirm.ask` as it did before this change
