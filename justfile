df *FLAGS:
    uv run python -m deepfellow.main {{FLAGS}}


test *FLAGS:
    uv run pytest --showlocals --tb=auto -ra --cov deepfellow --cov-branch --cov-report=term-missing --no-cov-on-fail {{FLAGS}}

ruff *FLAGS:
    uv run ruff check . {{FLAGS}}

ruff-format *FLAGS:
    uv run ruff format . {{FLAGS}}

mypy *FLAGS:
    uv run mypy deepfellow/ {{FLAGS}}


check: ruff ruff-format mypy

