# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Estimated VRAM of the models a suite install template puts on Infra, and the GPUs of this host."""

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from deepfellow.common.defaults import DOC_CHUNKER_STT_MODEL
from deepfellow.common.echo import echo
from deepfellow.common.system import run
from deepfellow.common.templates import PostStartAction

# Static model weights only, in GB: no KV cache for the configured context length and no runtime
# overhead. None of these is a measurement - each is a published estimate or derived from the weight
# size. Replace one with an `ollama ps` reading from a GPU host by editing it here.
MODEL_ESTIMATED_VRAM_GB: dict[str, float] = {
    # https://ai.google.dev/gemma/docs/core - E4B at Q4_0, weights only.
    "gemma4:e4b": 4.5,
    # F16 weights, 335M parameters * 2 bytes ~ the 670 MB download on https://ollama.com/library/mxbai-embed-large;
    # https://willitrunai.com/can-run/mxbai-embed-large-on-rtx-4000-ada-20gb derives the same 0.7 GB.
    "mxbai-embed-large": 0.7,
    # https://github.com/SYSTRAN/faster-whisper benchmarks large-v2 at fp16 with 4525 MB; large-v3 has the same size.
    DOC_CHUNKER_STT_MODEL: 4.5,
}


def _template_models(infra_post_start_actions: Sequence[PostStartAction]) -> list[str]:
    """Names of the models the actions install onto a service, in order, without duplicates.

    Models of the "custom" service (e.g. Doc Chunker) are skipped: they are not loaded onto the GPU.
    """
    models = (
        action["kwargs"]["model_name"]
        for action in infra_post_start_actions
        if action["function"] == "infra.model.install" and action["kwargs"]["service_name"] != "custom"
    )
    return list(dict.fromkeys(models))


@dataclass(frozen=True)
class VramEstimate:
    """Estimated VRAM of the models a template installs."""

    models: dict[str, float]
    """Estimated VRAM in GB of each model that has an estimate, in install order."""
    unestimated: list[str]
    """Models without an estimate, left out of the total."""

    @property
    def total_gb(self) -> float:
        """Total estimated VRAM in GB; a lower bound when some model has no estimate."""
        return sum(self.models.values())


@dataclass(frozen=True)
class GpuInfo:
    """A GPU of this host."""

    name: str
    memory_gb: float
    """Total VRAM in decimal GB, the unit of the model estimates."""


_NVIDIA_SMI_TIMEOUT_S = 5
"""Seconds to wait for `nvidia-smi`; it can hang on a broken driver."""

_BYTES_PER_MIB = 1024 * 1024


class _GpuQueryError(Exception):
    """`nvidia-smi` failed to report the GPUs."""


def estimate_vram(infra_post_start_actions: Sequence[PostStartAction]) -> VramEstimate:
    """Estimate the VRAM of the models the infra post-start actions install.

    Args:
        infra_post_start_actions: The resolved infra template's post-start actions.

    Returns:
        The estimate of each model found in `MODEL_ESTIMATED_VRAM_GB`, and the models without one.
    """
    models = _template_models(infra_post_start_actions)
    return VramEstimate(
        models={model: MODEL_ESTIMATED_VRAM_GB[model] for model in models if model in MODEL_ESTIMATED_VRAM_GB},
        unestimated=[model for model in models if model not in MODEL_ESTIMATED_VRAM_GB],
    )


def detect_gpus() -> list[GpuInfo]:
    """Return the NVIDIA GPUs of this host, as `nvidia-smi` reports them.

    Returns:
        One entry per GPU; empty when `nvidia-smi` is missing, fails, or prints nothing parseable.
    """
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        output = run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            raises=_GpuQueryError,
            timeout=_NVIDIA_SMI_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        echo.debug(f"nvidia-smi did not answer within {_NVIDIA_SMI_TIMEOUT_S} s")
        return []
    except _GpuQueryError as exc:
        # nvidia-smi prints its errors to stdout, while the exception carries only stderr.
        cause = exc.__cause__
        stdout = cause.stdout if isinstance(cause, subprocess.CalledProcessError) else None
        echo.debug(f"Could not read GPUs with nvidia-smi: {(str(exc) or stdout or '').strip()}")
        return []

    gpus = []
    for line in (output or "").splitlines():
        name, _, memory_mib = line.rpartition(",")
        try:
            gpus.append(GpuInfo(name=name.strip(), memory_gb=float(memory_mib) * _BYTES_PER_MIB / 1e9))
        except ValueError:
            echo.debug(f"Skipping unparseable nvidia-smi line: {line!r}")
    return [gpu for gpu in gpus if gpu.name]


def print_vram_estimate(infra_post_start_actions: Sequence[PostStartAction]) -> None:
    """Print the estimated VRAM of each model the infra post-start actions install, the total, and this host's GPUs.

    A model without an entry in `MODEL_ESTIMATED_VRAM_GB` is left out of the total and named as having
    no estimate, so the total reads as a lower bound. Prints nothing when no model has an estimate.

    Args:
        infra_post_start_actions: The resolved infra template's post-start actions.
    """
    estimate = estimate_vram(infra_post_start_actions)
    if not estimate.models:
        return

    lines = ["Estimated VRAM of the models this install sets up, if run on GPU:"]
    lines.extend(f"  {model}: ~{vram:.1f} GB" for model, vram in estimate.models.items())
    lines.append(f"Total: ~{estimate.total_gb:.1f} GB")
    if estimate.unestimated:
        lines.append(f"No estimate for: {', '.join(estimate.unestimated)} (not included in the total).")
    lines.append(
        "This covers model weights only. The KV cache for the configured context length and runtime overhead "
        "are not included, so real usage will be higher."
    )
    lines.extend(f"Detected GPU: {gpu.name} ({gpu.memory_gb:.1f} GB VRAM)" for gpu in detect_gpus())
    echo.info("\n".join(lines))
