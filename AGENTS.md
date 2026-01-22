# AGENTS.md

This file provides guidelines for agentic coding agents operating in this repository.

## Build/Lint/Test Commands

All commands should be run using `just` (makefile-like tool):

- Run all tests: `just test`
- Run a single test file: `just test tests/infra/test_service.py`
- Run a specific test: `just test tests/infra/test_service.py::test_function_name`
- Lint code: `just ruff`
- Format code: `just ruff-format`
- Type check: `just mypy`
- Run all checks: `just check`

## CLI Commands

The CLI has two main modules defined in the `deepfellow/` directory:

- `@deepfellow/infra/` - Infrastructure module with commands for managing infrastructure resources
- `@deepfellow/server/` - Server module with commands for managing server resources

Use the following commands to display subcommands:

- `just df server --help` - Show all server module subcommands
- `just df infra --help` - Show all infra module subcommands

## Command Structure

Final subcommands are always placed in separate files in their respective command group directories. For example:

- `@deepfellow/infra/stop.py` is a `infra stop` command placed in the `infra` command group directory
- `@deepfellow/server/project/get.py` is a `server project get` command placed in the `server project` command group directory

Connecting a final subcommand is done in command group's `__init__.py` file. For example:

```
from .stop import app as stop_app
app.add_typer(stop_app)
```

Connecting a subgroup to a group command is happening by adding a name. For example, we have a subgroup directory `@deepfellow/server/project/` with an `__init__.py` file. We connect it in `server` command group's `__init__.py` by providing its name and help message:

```
from .project import app as project_app
app.add_typer(project_app, name="project", help="Manage Projects.")
```

## Common Modules

The following common modules are used across both modules:

- `@deepfellow/common/` - Shared utilities used in both server and infra command groups
  - Contains shared functionality like configuration, validation, Docker helpers, and system utilities
  - Provides common patterns and helpers for both infrastructure and server commands

- `@deepfellow/infra/utils/` - Infrastructure-specific utilities for the infra command group
  - Contains helpers specific to infrastructure management
  - Includes modules like docker.py, options.py, and validation.py for infrastructure operations

- `@deepfellow/server/utils/` - Server-specific utilities for the server command group
  - Contains helpers specific to server management
  - Includes modules for configuration, Docker operations, login utilities, and other server-specific functionality

## Code Style Guidelines

### Imports
- Use isort for import sorting with configured sections
- Imports should be grouped in order: future, standard-library, third-party, first-party, local-folder
- Import statements should be sorted alphabetically within each section

### Formatting
- Use ruff formatter with line length of 120 characters
- Indent with 4 spaces
- Follow PEP8 style guidelines

### Types
- Use type hints for all function parameters, return values, and variables
- Use proper typing annotations (Optional, List, Dict, etc.)
- Use ClassVar for mutable class attributes

### Naming Conventions
- Use snake_case for variables and functions
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Private attributes/methods should start with underscore

### Error Handling
- Use try/except blocks for handling expected exceptions
- Include meaningful error messages
- Use appropriate exception types
- Follow the principle of explicit over implicit

### Documentation
- Use docstrings with Google-style formatting
- All public functions should have docstrings
- Classes may have docstrings if helpful
- Keep docstrings concise and descriptive

## Testing
- Write tests using pytest framework
- Tests should be in `tests/` directory following the module structure
- Each test file should be named `test_<module>.py`
- Use fixtures for test setup/teardown
- Tests should be isolated and not depend on each other

## Development Environment
- Install dependencies using `uv pip install -e .`
- Use virtual environment (`.venv` directory)
- Configure pre-commit hooks with `pre-commit install`
- All development should be done in the virtual environment

## Git Workflow
- The project uses GitLab for version control
- Install and configure `glab` CLI tool for GitLab operations:
  - `glab` is the GitLab CLI that allows managing GitLab resources from command line
  - Use `glab branch create` to create branches for issues if not existing
  - Use `glab mr create` to create merge requests
