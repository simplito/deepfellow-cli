# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import json
from unittest import mock

import pytest

from deepfellow.common.templates import PostStartAction
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES
from deepfellow.suite.utils.vram import MODEL_ESTIMATED_VRAM_GB, print_vram_estimate

ESTIMATES = {"model-a": 1.5, "model-b": 2.0}


def _model_action(model_name: str, service_name: str = "ollama") -> PostStartAction:
    return {"function": "infra.model.install", "kwargs": {"service_name": service_name, "model_name": model_name}}


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_lists_each_model_with_total(mock_echo: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("model-b")]

    print_vram_estimate(actions)

    assert mock_echo.info.call_count == 1
    message = mock_echo.info.call_args.args[0]
    assert "model-a: ~1.5 GB" in message
    assert "model-b: ~2.0 GB" in message
    assert "Total: ~3.5 GB" in message
    assert "No estimate for" not in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_states_it_covers_weights_only(mock_echo: mock.MagicMock):
    actions = [_model_action("model-a")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert "This covers model weights only." in message
    assert "KV cache" in message
    assert "runtime overhead" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_skips_custom_service_models(mock_echo: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("doc_chunker", service_name="custom")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert "doc_chunker" not in message
    assert "Total: ~1.5 GB" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_ignores_non_model_actions(mock_echo: mock.MagicMock):
    service_action: PostStartAction = {
        "function": "infra.service.install",
        "kwargs": {"name": "ollama", "spec": json.dumps({})},
    }
    actions = [service_action, _model_action("model-a")]

    print_vram_estimate(actions)

    assert "Total: ~1.5 GB" in mock_echo.info.call_args.args[0]


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_counts_a_repeated_model_once(mock_echo: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("model-a")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert message.count("model-a: ~1.5 GB") == 1
    assert "Total: ~1.5 GB" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_names_unknown_model_and_excludes_it_from_total(mock_echo: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("model-unknown")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert "model-a: ~1.5 GB" in message
    assert "Total: ~1.5 GB" in message
    assert "No estimate for: model-unknown" in message
    assert "model-unknown: ~" not in message


@pytest.mark.parametrize(
    "actions",
    [
        [],
        [_model_action("model-unknown")],
        [_model_action("model-a", service_name="custom")],
    ],
)
@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_prints_nothing_without_a_known_model(
    mock_echo: mock.MagicMock, actions: list[PostStartAction]
):
    print_vram_estimate(actions)

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_workspace_template_lists_every_model(mock_echo: mock.MagicMock):
    actions = BUILTIN_TEMPLATES["workspace"]["post_start_actions"]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    for model, vram in MODEL_ESTIMATED_VRAM_GB.items():
        assert f"{model}: ~{vram:.1f} GB" in message
    assert "No estimate for" not in message


def test_model_estimated_vram_covers_every_model_the_workspace_template_installs():
    actions = BUILTIN_TEMPLATES["workspace"]["post_start_actions"]
    models = {
        action["kwargs"]["model_name"]
        for action in actions
        if action["function"] == "infra.model.install" and action["kwargs"]["service_name"] != "custom"
    }

    missing = models - set(MODEL_ESTIMATED_VRAM_GB)

    assert missing == set()
