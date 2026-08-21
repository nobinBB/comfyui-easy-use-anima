# SPDX-License-Identifier: GPL-3.0-only
"""Discover Anima diffusion models from their Safetensors architecture keys."""

from __future__ import annotations

from pathlib import Path

import folder_paths
from safetensors import safe_open


_BACKBONE_SIGNATURE = "blocks.0.mlp.layer1.weight"
_ANIMA_ADAPTER_SIGNATURE = "llm_adapter.blocks.0.cross_attn.q_proj.weight"
_MODEL_CACHE: dict[str, tuple[int, int, bool]] = {}


def _has_anima_architecture(model_path: str) -> bool:
    """Check only the Safetensors header; tensor data is never loaded."""
    path = Path(model_path)
    if path.suffix.casefold() != ".safetensors":
        return False

    try:
        stat = path.stat()
    except OSError:
        return False

    cache_key = str(path.resolve())
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    cached = _MODEL_CACHE.get(cache_key)
    if cached is not None and cached[:2] == fingerprint:
        return cached[2]

    is_anima = False
    try:
        with safe_open(str(path), framework="pt", device="cpu") as file:
            keys = set(file.keys())

        # ComfyUI detects Cosmos Predict2 from the backbone key, then identifies
        # Anima by the LLM adapter key. Requiring the same prefix avoids matching
        # unrelated tensors that happen to have a similar suffix.
        for key in keys:
            if not key.endswith(_ANIMA_ADAPTER_SIGNATURE):
                continue
            prefix = key[: -len(_ANIMA_ADAPTER_SIGNATURE)]
            if f"{prefix}{_BACKBONE_SIGNATURE}" in keys:
                is_anima = True
                break
    # A broken or unsupported model must not prevent ComfyUI from building the
    # node list. safetensors-rust uses its own exception type, so keep this
    # boundary intentionally broad and simply omit files that cannot be read.
    except Exception:
        is_anima = False

    _MODEL_CACHE[cache_key] = (*fingerprint, is_anima)
    return is_anima


def anima_model_names() -> list[str]:
    """Return Anima models regardless of their file or directory names."""
    matches = []
    for name in folder_paths.get_filename_list("diffusion_models"):
        model_path = folder_paths.get_full_path("diffusion_models", name)
        if model_path and _has_anima_architecture(model_path):
            matches.append(name)
    return matches
