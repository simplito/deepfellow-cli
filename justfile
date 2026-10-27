df *FLAGS:
    uv run python -m deepfellow.main {{FLAGS}}


test *FLAGS:
    uv run pytest --showlocals --tb=auto -ra --cov deepfellow --cov-branch --cov-report=term-missing --no-cov-on-fail {{FLAGS}}

test-unit *FLAGS:
    uv run pytest --showlocals --tb=auto -ra --cov deepfellow --cov-branch --cov-report=term-missing --no-cov-on-fail tests/unit {{FLAGS}}

test-integration *FLAGS:
    uv run pytest --showlocals --tb=auto -ra tests/integration {{FLAGS}}

test-smoke *FLAGS:
    uv run pytest --showlocals --tb=auto -ra tests/smoke {{FLAGS}}

test-e2e *FLAGS:
    uv run pytest --showlocals --tb=auto -ra tests/e2e {{FLAGS}}

ruff *FLAGS:
    uv run ruff check deepfellow/ tests/ {{FLAGS}}

ruff-format *FLAGS:
    uv run ruff format . {{FLAGS}}

mypy *FLAGS:
    uv run mypy deepfellow/ tests/ {{FLAGS}}

pyright:
    uv run pyright

license-check *FLAGS:
    uv run scripts/check_license_header.py {{FLAGS}}

deptry *FLAGS:
    uv run deptry . {{FLAGS}}

check: ruff ruff-format mypy pyright license-check deptry

changelog-check:
    sh scripts/changelog_check.sh
