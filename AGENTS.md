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