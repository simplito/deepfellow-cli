# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import json
import subprocess
from unittest import mock

import pytest

from deepfellow.common.templates import PostStartAction
from deepfellow.infra.utils.templates import BUILTIN_TEMPLATES
from deepfellow.suite.utils.vram import (
    MODEL_ESTIMATED_VRAM_GB,
    GpuInfo,
    VramEstimate,
    _GpuQueryError,
    detect_gpus,
    estimate_vram,
    print_vram_estimate,
)

ESTIMATES = {"model-a": 1.5, "model-b": 2.0}


def _model_action(model_name: str, service_name: str = "ollama") -> PostStartAction:
    return {"function": "infra.model.install", "kwargs": {"service_name": service_name, "model_name": model_name}}


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_lists_each_model_with_total(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("model-b")]

    print_vram_estimate(actions)

    assert mock_echo.info.call_count == 1
    message = mock_echo.info.call_args.args[0]
    assert "model-a: ~1.5 GB" in message
    assert "model-b: ~2.0 GB" in message
    assert "Total: ~3.5 GB" in message
    assert "No estimate for" not in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_states_it_covers_weights_only(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    actions = [_model_action("model-a")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert "This covers model weights only." in message
    assert "KV cache" in message
    assert "runtime overhead" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_skips_custom_service_models(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("doc_chunker", service_name="custom")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert "doc_chunker" not in message
    assert "Total: ~1.5 GB" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_ignores_non_model_actions(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    service_action: PostStartAction = {
        "function": "infra.service.install",
        "kwargs": {"name": "ollama", "spec": json.dumps({})},
    }
    actions = [service_action, _model_action("model-a")]

    print_vram_estimate(actions)

    assert "Total: ~1.5 GB" in mock_echo.info.call_args.args[0]


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_counts_a_repeated_model_once(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    actions = [_model_action("model-a"), _model_action("model-a")]

    print_vram_estimate(actions)

    message = mock_echo.info.call_args.args[0]
    assert message.count("model-a: ~1.5 GB") == 1
    assert "Total: ~1.5 GB" in message


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_names_unknown_model_and_excludes_it_from_total(
    mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock
):
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
@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_prints_nothing_without_a_known_model(
    mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock, actions: list[PostStartAction]
):
    print_vram_estimate(actions)

    assert mock_echo.info.call_count == 0


@mock.patch("deepfellow.suite.utils.vram.detect_gpus", return_value=[])
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_workspace_template_lists_every_model(
    mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock
):
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


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
@mock.patch(
    "deepfellow.suite.utils.vram.detect_gpus", return_value=[GpuInfo(name="NVIDIA RTX 4000 Ada", memory_gb=20.0)]
)
@mock.patch("deepfellow.suite.utils.vram.echo")
def test_print_vram_estimate_names_detected_gpu(mock_echo: mock.MagicMock, mock_detect_gpus: mock.MagicMock):
    actions = [_model_action("model-a")]

    print_vram_estimate(actions)

    assert "Detected GPU: NVIDIA RTX 4000 Ada (20.0 GB VRAM)" in mock_echo.info.call_args.args[0]


@mock.patch.dict(MODEL_ESTIMATED_VRAM_GB, ESTIMATES, clear=True)
def test_estimate_vram_returns_estimates_and_unestimated_models():
    actions = [_model_action("model-a"), _model_action("model-unknown"), _model_action("model-b")]

    result = estimate_vram(actions)

    assert result == VramEstimate(models={"model-a": 1.5, "model-b": 2.0}, unestimated=["model-unknown"])
    assert result.total_gb == 3.5


@mock.patch("deepfellow.suite.utils.vram.run")
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value=None)
def test_detect_gpus_returns_empty_list_without_nvidia_smi(mock_which: mock.MagicMock, mock_run: mock.MagicMock):
    result = detect_gpus()

    assert result == []
    assert mock_run.call_count == 0


@mock.patch(
    "deepfellow.suite.utils.vram.run", return_value="NVIDIA RTX 4000 Ada Generation, 20475\nNVIDIA A100, 81920\n"
)
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_parses_name_and_memory(mock_which: mock.MagicMock, mock_run: mock.MagicMock):
    result = detect_gpus()

    assert result == [
        GpuInfo(name="NVIDIA RTX 4000 Ada Generation", memory_gb=20475 * 1024 * 1024 / 1e9),
        GpuInfo(name="NVIDIA A100", memory_gb=81920 * 1024 * 1024 / 1e9),
    ]
    assert mock_run.call_args == mock.call(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        raises=_GpuQueryError,
        timeout=5,
    )


@mock.patch("deepfellow.suite.utils.vram.run", return_value="NVIDIA A100, 81920\n")
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_reports_memory_in_decimal_gb(mock_which: mock.MagicMock, mock_run: mock.MagicMock):
    result = detect_gpus()

    assert round(result[0].memory_gb, 1) == 85.9


@mock.patch("deepfellow.suite.utils.vram.run", side_effect=_GpuQueryError("no devices"))
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_returns_empty_list_when_nvidia_smi_fails(mock_which: mock.MagicMock, mock_run: mock.MagicMock):
    result = detect_gpus()

    assert result == []


def _gpu_query_error_with_stdout(stdout: str) -> _GpuQueryError:
    error = _GpuQueryError("")
    error.__cause__ = subprocess.CalledProcessError(9, ["nvidia-smi"], output=stdout)
    return error


@mock.patch("deepfellow.suite.utils.vram.echo")
@mock.patch(
    "deepfellow.suite.utils.vram.run",
    side_effect=_gpu_query_error_with_stdout("NVIDIA-SMI has failed because it couldn't communicate with the driver\n"),
)
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_logs_nvidia_smi_stdout_when_stderr_is_empty(
    mock_which: mock.MagicMock, mock_run: mock.MagicMock, mock_echo: mock.MagicMock
):
    result = detect_gpus()

    assert result == []
    assert mock_echo.debug.call_args == mock.call(
        "Could not read GPUs with nvidia-smi: NVIDIA-SMI has failed because it couldn't communicate with the driver"
    )


@mock.patch("deepfellow.suite.utils.vram.echo")
@mock.patch("deepfellow.suite.utils.vram.run", side_effect=_GpuQueryError("no devices"))
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_logs_nvidia_smi_stderr(
    mock_which: mock.MagicMock, mock_run: mock.MagicMock, mock_echo: mock.MagicMock
):
    result = detect_gpus()

    assert result == []
    assert mock_echo.debug.call_args == mock.call("Could not read GPUs with nvidia-smi: no devices")


@mock.patch("deepfellow.suite.utils.vram.echo")
@mock.patch("deepfellow.suite.utils.vram.run", side_effect=subprocess.TimeoutExpired(["nvidia-smi"], 5))
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_returns_empty_list_when_nvidia_smi_times_out(
    mock_which: mock.MagicMock, mock_run: mock.MagicMock, mock_echo: mock.MagicMock
):
    result = detect_gpus()

    assert result == []
    assert mock_echo.debug.call_args == mock.call("nvidia-smi did not answer within 5 s")


@mock.patch("deepfellow.suite.utils.vram.run", return_value="NVIDIA A100, [N/A]\n, 1024\nno comma\nNVIDIA L4, 23034\n")
@mock.patch("deepfellow.suite.utils.vram.shutil.which", return_value="/usr/bin/nvidia-smi")
def test_detect_gpus_skips_unparseable_lines(mock_which: mock.MagicMock, mock_run: mock.MagicMock):
    result = detect_gpus()

    assert result == [GpuInfo(name="NVIDIA L4", memory_gb=23034 * 1024 * 1024 / 1e9)]
