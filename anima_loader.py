# SPDX-License-Identifier: GPL-3.0-only
"""Anima-only EasyLoader compatible with ComfyUI-Easy-Use pipelines.

The loader deliberately keeps the diffusion model and text encoder paths
separate. In particular, it never loads a Stable Diffusion checkpoint.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import folder_paths
from nodes import MAX_RESOLUTION, NODE_CLASS_MAPPINGS as CORE_NODES

try:
    from .anima_model_filter import anima_model_names
except ImportError:  # Direct module loading used by tests and development tools.
    from anima_model_filter import anima_model_names


CUSTOM_RESOLUTION = "width x height (custom)"
FALLBACK_BASE_RESOLUTIONS = [
    ("width", "height"),
    (512, 512),
    (512, 768),
    (576, 1024),
    (768, 512),
    (768, 768),
    (768, 1024),
    (768, 1280),
    (768, 1344),
    (768, 1536),
    (816, 1920),
    (832, 1152),
    (832, 1216),
    (896, 1152),
    (896, 1088),
    (1024, 1024),
    (1024, 576),
    (1024, 768),
    (1080, 1920),
    (1440, 2560),
    (1088, 896),
    (1216, 832),
    (1152, 832),
    (1152, 896),
    (1280, 768),
    (1344, 768),
    (1536, 640),
    (1536, 768),
    (1920, 816),
    (1920, 1080),
    (2560, 1440),
]


def _read_easy_use_base_resolutions() -> list[tuple[Any, Any]]:
    custom_nodes_dir = Path(__file__).resolve().parent.parent
    candidates = [
        custom_nodes_dir / "comfyui-easy-use" / "py" / "config.py",
        custom_nodes_dir / "ComfyUI-Easy-Use" / "py" / "config.py",
    ]
    for config_path in candidates:
        if not config_path.is_file():
            continue
        try:
            tree = ast.parse(config_path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                if any(
                    isinstance(target, ast.Name) and target.id == "BASE_RESOLUTIONS"
                    for target in node.targets
                ):
                    value = ast.literal_eval(node.value)
                    if isinstance(value, list) and value:
                        return value
        except (OSError, SyntaxError, ValueError):
            continue
    return list(FALLBACK_BASE_RESOLUTIONS)


def _format_resolutions(base_resolutions: list[tuple[Any, Any]]) -> list[str]:
    return [
        CUSTOM_RESOLUTION
        if width == "width" and height == "height"
        else f"{width} x {height}"
        for width, height in base_resolutions
    ]


ANIMA_RESOLUTIONS = _format_resolutions(_read_easy_use_base_resolutions())


def _vae_input_options() -> tuple[list[str], dict[str, Any]]:
    names = folder_paths.get_filename_list("vae")
    qwen_names = [name for name in names if "qwen" in name.lower()]
    ordered_names = qwen_names + [name for name in names if name not in qwen_names]
    preferred = next(
        (name for name in qwen_names if name.lower().endswith("qwen_image_vae.safetensors")),
        qwen_names[0] if qwen_names else (names[0] if names else None),
    )
    options: dict[str, Any] = {
        "tooltip": (
            "Anima requires a 16-channel Qwen Image VAE; normally "
            "qwen_image_vae.safetensors. Incompatible SD VAEs are rejected."
        )
    }
    if preferred is not None:
        options["default"] = preferred
    return ordered_names, options


def _core_node(name: str) -> Any:
    node_class = CORE_NODES.get(name)
    if node_class is None:
        raise RuntimeError(
            f"ComfyUI core node '{name}' is unavailable. "
            "Update ComfyUI to a version with native Anima support."
        )
    return node_class()


def _resolve_size(resolution: str, width: int, height: int) -> tuple[int, int]:
    if resolution == CUSTOM_RESOLUTION:
        return width, height
    try:
        parsed_width, parsed_height = resolution.split(" x ", maxsplit=1)
        return int(parsed_width), int(parsed_height)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid resolution: {resolution!r}") from error


def _model_config(model: Any) -> Any:
    return getattr(getattr(model, "model", None), "model_config", None)


def _assert_anima_model(model: Any, model_name: str) -> None:
    config = _model_config(model)
    image_model = getattr(config, "unet_config", {}).get("image_model") if config else None
    is_anima = image_model == "anima" or (
        config is not None and "anima" in type(config).__name__.lower()
    )
    if not is_anima:
        raise RuntimeError(
            f"'{model_name}' was not detected as an Anima diffusion model. "
            "Choose an Anima model from models/diffusion_models and update ComfyUI."
        )


def _assert_anima_clip(clip: Any, clip_name: str) -> None:
    tokenizer = getattr(clip, "tokenizer", None)
    is_anima = tokenizer is not None and (
        "anima" in type(tokenizer).__name__.lower()
        or hasattr(tokenizer, "qwen3_06b")
    )
    if not is_anima:
        raise RuntimeError(
            f"'{clip_name}' was not detected as the Anima Qwen3 0.6B text encoder. "
            "Choose qwen_3_06b_base.safetensors (or a compatible Anima encoder) "
            "from models/text_encoders."
        )


def _assert_anima_vae(vae: Any, vae_name: str) -> None:
    latent_channels = getattr(vae, "latent_channels", None)
    if latent_channels != 16:
        raise RuntimeError(
            f"'{vae_name}' is not compatible with Anima: expected a 16-channel "
            f"Qwen Image VAE, but this VAE uses {latent_channels!r} latent channels. "
            "Choose qwen_image_vae.safetensors or another compatible Qwen Image VAE."
        )


class EasyAnimaFullLoader:
    """Load a complete native Anima pipeline without an SD checkpoint path."""

    @classmethod
    def INPUT_TYPES(cls):
        vae_names, vae_options = _vae_input_options()
        return {
            "required": {
                "model_name": (
                    anima_model_names(),
                    {
                        "tooltip": (
                            "Anima diffusion model from models/diffusion_models; "
                            "for example anima-base-v1.0.safetensors."
                        )
                    },
                ),
                "weight_dtype": (
                    ["default", "fp8_e4m3fn", "fp8_e4m3fn_fast", "fp8_e5m2"],
                    {"default": "default", "advanced": True},
                ),
                "clip_name": (
                    folder_paths.get_filename_list("text_encoders"),
                    {
                        "tooltip": (
                            "Anima Qwen3 0.6B text encoder from models/text_encoders; "
                            "normally qwen_3_06b_base.safetensors."
                        )
                    },
                ),
                "clip_device": (
                    ["default", "cpu"],
                    {"default": "default", "advanced": True},
                ),
                "vae_name": (
                    vae_names,
                    vae_options,
                ),
                "resolution": (ANIMA_RESOLUTIONS, {"default": "1024 x 1024"}),
                "empty_latent_width": (
                    "INT",
                    {"default": 1024, "min": 64, "max": MAX_RESOLUTION, "step": 8},
                ),
                "empty_latent_height": (
                    "INT",
                    {"default": 1024, "min": 64, "max": MAX_RESOLUTION, "step": 8},
                ),
                "batch_size": (
                    "INT",
                    {"default": 1, "min": 1, "max": 4096},
                ),
            },
        }

    RETURN_TYPES = (
        "PIPE_LINE",
        "MODEL",
        "VAE",
        "CLIP",
        "LATENT",
        anima_model_names(),
        folder_paths.get_filename_list("vae"),
    )
    RETURN_NAMES = (
        "pipe",
        "model",
        "vae",
        "clip",
        "latent",
        "model_name",
        "vae_name",
    )
    FUNCTION = "load_anima"
    CATEGORY = "EasyUse-Anima/Loaders"
    DESCRIPTION = (
        "An Anima-only EasyLoader. Loads the diffusion model, Qwen3 0.6B "
        "text encoder, and VAE separately; it has no SD checkpoint or CLIP "
        "override path."
    )

    def load_anima(
        self,
        model_name: str,
        weight_dtype: str,
        clip_name: str,
        clip_device: str,
        vae_name: str,
        resolution: str,
        empty_latent_width: int,
        empty_latent_height: int,
        batch_size: int,
    ):
        model = _core_node("UNETLoader").load_unet(model_name, weight_dtype)[0]
        _assert_anima_model(model, model_name)

        # "stable_diffusion" is ComfyUI's single-encoder auto-detection mode.
        # The loaded Qwen3 0.6B state dict is detected as Anima by core.  No SD
        # checkpoint CLIP and no external CLIP override is ever consulted.
        clip = _core_node("CLIPLoader").load_clip(
            clip_name, type="stable_diffusion", device=clip_device
        )[0]
        _assert_anima_clip(clip, clip_name)

        vae = _core_node("VAELoader").load_vae(vae_name)[0]
        _assert_anima_vae(vae, vae_name)

        width, height = _resolve_size(
            resolution, empty_latent_width, empty_latent_height
        )
        latent = _core_node("EmptyLatentImage").generate(
            width, height, batch_size
        )[0]

        pipe = {
            "model": model,
            "positive": None,
            "negative": None,
            "vae": vae,
            "clip": clip,
            "samples": latent,
            "images": None,
            "loader_settings": {
                "loader": "easy-use-anima",
                "model_family": "anima",
                "model_name": model_name,
                "weight_dtype": weight_dtype,
                "clip_name": clip_name,
                "clip_device": clip_device,
                "vae_name": vae_name,
                "resolution": resolution,
                "empty_latent_width": width,
                "empty_latent_height": height,
                "batch_size": batch_size,
            },
        }

        return (
            pipe,
            model,
            vae,
            clip,
            latent,
            model_name,
            vae_name,
        )


NODE_CLASS_MAPPINGS = {
    "easy animaLoaderV2": EasyAnimaFullLoader,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaLoaderV2": "EasyLoader (Full) - Anima",
}
