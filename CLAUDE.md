# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test/Lint Commands

All commands use `just` (task runner):

- `just check` — run all checks (ruff lint, ruff format, mypy, license headers)
- `just test` — run all tests with coverage
- `just test tests/infra/test_service.py` — single test file
- `just test tests/infra/test_service.py::test_function_name` — single test
- `just ruff` — lint
- `just ruff-format` — format
- `just mypy` — type check
- `just license-check` — verify license headers

## Code Style

- Ruff formatter: 120 char line length, 4-space indent
- Type hints required on all function parameters and return values
- Google-style docstrings on all public functions
- isort import ordering: future → stdlib → third-party → first-party → local
- All Python files must include the DeepFellow Free License header (enforced by `scripts/check_license_header.py`)

## Testing Conventions

- Use plain pytest functions — no TestClass
- Test file names: `test_<module>.py` (e.g., `tests/infra/test_service.py`)
- Directory structure mirrors source: `tests/common/`, `tests/infra/`, `tests/server/`
- Test names include function name + reason: `test_echoblock_run_success`, `test_list_workflows_returns_empty_list`
- Use **Arrange, Act, Assert** (AAA) pattern in function body
- Use `@mock.patch` decorators, not `with mock.patch` context managers
- No "magic" mock asserts — use `assert mocked.call_count == 1` and `assert mocked.call_args == mock.call(...)` instead of `mocked.assert_called_once_with(...)`
- Directory-scoped `conftest.py` for fixtures used only within one test directory

## CLI Architecture

Two Typer command groups under `deepfellow/`:
- `deepfellow/infra/` — infrastructure management commands
- `deepfellow/server/` — server management commands
- `deepfellow/common/` — shared utilities

Each final subcommand lives in its own file; wired in the group's `__init__.py`. See @AGENTS.md for details.

### Runtime state (`deepfellow/common/state.py`)

CLI-wide flags set by `main()` are stored in a module-level `AppState` singleton:

```python
from deepfellow.common.state import state

state.debug            # bool — --debug / --verbose / -v / -vv flag
state.yes              # bool — --yes / -y flag
state.non_interactive  # bool — --non-interactive flag
state.cli_config       # dict — parsed CLI config file
state.cli_config_file  # Path — path to CLI config file
state.cli_secrets_file  # Path — path to CLI secrets file
```

`main()` populates `state` once at startup. Every module — including all final subcommands — reads CLI flags from `state` directly. Subcommands no longer take a `ctx: typer.Context` parameter for this. **Never use `click.get_current_context()`.**

## Git Workflow

- GitLab-hosted; use `glab` CLI for branches and MRs
- Never merge MRs via CLI — merging is done manually in GitLab UI
- Never add `Co-Authored-By` lines to commit messages
- Never include `openspec/` or `.opencode/` files in git commits
