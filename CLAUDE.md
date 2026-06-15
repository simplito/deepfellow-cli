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
- `just df <args>` — run the CLI locally (e.g. `just df infra --help`)

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

Three Typer command groups under `deepfellow/`, all registered in `main.py`:
- `deepfellow/infra/` — infrastructure management (Docker Compose-based infra stack)
- `deepfellow/server/` — server management (DeepFellow Server API + Docker)
- `deepfellow/cli/` — CLI self-management (e.g., `cli update`)
- `deepfellow/common/` — shared utilities

Each final subcommand lives in its own file; wired in the group's `__init__.py`. See @AGENTS.md for details.

Subgroups (nested command groups within `infra/` and `server/`) use `name=` in `add_typer()`:
- `infra env`, `infra service`, `infra model`
- `server env`, `server organization`, `server project`

### User I/O (`deepfellow/common/echo.py`)

All output and prompting goes through the `echo` singleton (a `rich.Console` subclass):

```python
from deepfellow.common.echo import echo

echo.info(msg)          # informational
echo.success(msg)       # green ✅
echo.warning(msg)       # yellow ⚠️
echo.error(msg)         # red 💀
echo.debug(msg)         # only when state.debug=True
echo.confirm(msg)       # bool prompt; respects --non-interactive
echo.prompt(...)        # string prompt with optional validation
echo.prompt_until_valid(...)  # retries until validation passes
echo.choice(...)        # questionary select
```

Interactive mode (default) shows emojis and rich formatting. Non-interactive mode (`--non-interactive`) strips formatting and uses defaults or raises `typer.Exit(1)` if no default.

### Config and secrets files

Both files use `.env` format and live at `~/.deepfellow/`. Paths are in `state.cli_config_file` / `state.cli_secrets_file`.

- **Config** (`~/.deepfellow/config`): CLI preferences, e.g. `df_server_url`
- **Secrets** (`~/.deepfellow/secrets`): `DF_USER_TOKEN`, `DF_USER_REFRESH_TOKEN`

Environment variable keys use `DF_` prefix and `__` as nesting separator (e.g. `DF_VECTOR_DATABASE__PROVIDER__TYPE`). `config.py` provides `read_env_file`, `save_env_file`, `env_to_dict`, and `dict_to_env` for round-tripping.

### HTTP calls (`deepfellow/common/rest.py`)

REST helpers handle auth headers and common HTTP error codes centrally:

```python
from deepfellow.common import rest

server = rest.get_server_url(server_arg)   # resolves, saves, health-checks
data = rest.get(url, token)
data = rest.post(url, token, data={...})
rest.delete(url, token)
rest.make_request(method, url, token, data={...})
```

Server commands get a valid bearer token via `get_token(state.cli_secrets_file, server)` from `deepfellow/server/utils/login.py` — handles access token validation and refresh automatically.

### Shell commands (`deepfellow/common/system.py`)

Use `run()` for all subprocess calls — it strips `VIRTUAL_ENV`, handles debug reraise, and returns stdout or `None` on failure:

```python
from deepfellow.common.system import run

result = run(["docker", "ps"], capture_output=True)        # returns stdout or None
run(["docker", "compose", "up", "-d"], cwd=directory)     # raises on failure in debug mode
run(["cmd"], raises=MyError)                               # raises MyError on failure
```

### Docker Compose helpers (`deepfellow/common/docker.py`)

Infra and server commands build Docker Compose configs programmatically then persist them:

```python
from deepfellow.common.docker import load_compose_file, merge_services, save_compose_file

compose = load_compose_file(directory / "compose.yaml")           # dict or {"services": {}}
merged = merge_services(DOCKER_COMPOSE_SERVER, DOCKER_COMPOSE_QDRANT)  # combine service dicts
save_compose_file(merged, directory / "compose.yaml")             # writes YAML
```

All default Docker Compose service templates and constants (ports, images, env vars) live in `deepfellow/common/defaults.py`.

### Env subcommand helpers (`deepfellow/common/env.py`)

The `infra env` and `server env` command groups use shared utilities:

```python
from deepfellow.common.env import env_get, env_set, print_env_info, EnvMetadata

env_set(env_file, "DF_SOME_KEY", value)            # writes to .env file; adds DF_ prefix if missing
value = env_get(env_file, "DF_SOME_KEY")           # reads from .env file
```

`print_env_info(header, env_metadata, env_values)` renders a formatted info/doc view. `EnvMetadata(description, sensitive)` marks fields for display — sensitive values show as `*****` unless `show_secret=True`.

### Infra directory option (`deepfellow/infra/utils/options.py`)

All infra commands that operate on a local install share a standard `--directory` option:

```python
from deepfellow.infra.utils.options import directory_option

def my_command(directory: Path = directory_option(exists=True)) -> None: ...
```

`exists=True` enables Typer path validation (readable, writable, must exist). Default is `~/.deepfellow/infra`.

### Error handling pattern

```python
from deepfellow.common.exceptions import reraise_if_debug

try:
    ...
except SomeError as exc:
    echo.error("Human-readable message")
    reraise_if_debug(exc)  # re-raises in debug mode, otherwise typer.Exit(1)
```

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
