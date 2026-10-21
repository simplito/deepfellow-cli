# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Estimated VRAM of the models a suite install template puts on Infra."""

from collections.abc import Sequence

from deepfellow.common.defaults import DOC_CHUNKER_STT_MODEL
from deepfellow.common.echo import echo
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


def print_vram_estimate(infra_post_start_actions: Sequence[PostStartAction]) -> None:
    """Print the estimated VRAM of each model the infra post-start actions install, and the total.

    A model without an entry in `MODEL_ESTIMATED_VRAM_GB` is left out of the total and named as having
    no estimate, so the total reads as a lower bound. Prints nothing when no model has an estimate.

    Args:
        infra_post_start_actions: The resolved infra template's post-start actions.
    """
    models = _template_models(infra_post_start_actions)
    estimated = [model for model in models if model in MODEL_ESTIMATED_VRAM_GB]
    if not estimated:
        return

    lines = ["Estimated VRAM of the models this install sets up, if run on GPU:"]
    lines.extend(f"  {model}: ~{MODEL_ESTIMATED_VRAM_GB[model]:.1f} GB" for model in estimated)
    lines.append(f"Total: ~{sum(MODEL_ESTIMATED_VRAM_GB[model] for model in estimated):.1f} GB")
    unestimated = [model for model in models if model not in MODEL_ESTIMATED_VRAM_GB]
    if unestimated:
        lines.append(f"No estimate for: {', '.join(unestimated)} (not included in the total).")
    lines.append(
        "This covers model weights only. The KV cache for the configured context length and runtime overhead "
        "are not included, so real usage will be higher."
    )
    echo.info("\n".join(lines))
