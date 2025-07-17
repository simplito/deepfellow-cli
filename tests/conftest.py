from unittest.mock import Mock

import pytest
from typer import Context


@pytest.fixture
def context() -> Context:
    ctx = Mock(spec=Context)
    ctx.obj = {}
    return ctx
