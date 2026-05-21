---
name: verify
description: Run all linting, formatting, type checking, and tests to verify the project is in a good state.
---

Run the full verification suite for this project. Execute each step and report results:

1. Run `just check` to execute all static checks (ruff lint, ruff format check, mypy, license headers)
2. Run `just test` to execute the full test suite with coverage

If any step fails, analyze the output and report what needs to be fixed. Do not attempt to fix issues automatically — just report them clearly.
