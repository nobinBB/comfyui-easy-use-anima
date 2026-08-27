# SPDX-License-Identifier: GPL-3.0-only
"""Scale a latent by decoding, resizing, and re-encoding with a VAE."""

from __future__ import annotations

import comfy.utils
import torch


UPSCALE_METHODS = ("lanczos", "bislerp")


class LatentUpscaleWithVAEBy:
    """Combine image-size calculation and VAE latent upscaling in one node."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent": ("LATENT",),
                "vae": ("VAE",),
                "scale_by": (
                    "FLOAT",
                    {"default": 1.25, "min": 0.01, "max": 8.0, "step": 0.01},
                ),
                "upscale_method": (UPSCALE_METHODS, {"default": "lanczos"}),
                "bislerp_ratio": (
                    "FLOAT",
                    {
                        "default": 0.50,
                        "min": 0.00,
                        "max": 1.00,
                        "step": 0.01,
                        "round": 0.01,
                    },
                ),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "upscale"
    CATEGORY = "EasyUse-Anima/Latent"
    DESCRIPTION = (
        "Decodes a latent with the selected VAE, resizes the decoded image by "
        "scale_by, and encodes it back to a latent."
    )

    def upscale(
        self,
        latent,
        vae,
        scale_by: float,
        upscale_method: str,
        bislerp_ratio: float = 0.50,
    ):
        if "samples" not in latent:
            raise ValueError("The LATENT input does not contain a 'samples' tensor.")

        source_samples = latent["samples"]
        decoded = vae.decode(source_samples)
        image_samples = decoded.movedim(-1, 1)
        target_width = max(1, round(image_samples.shape[-1] * float(scale_by)))
        target_height = max(1, round(image_samples.shape[-2] * float(scale_by)))
        if upscale_method == "bislerp":
            ratio = round(max(0.0, min(1.0, float(bislerp_ratio))), 2)
            if ratio <= 0.0:
                scaled_samples = comfy.utils.common_upscale(
                    image_samples, target_width, target_height, "lanczos", "disabled"
                )
            elif ratio >= 1.0:
                scaled_samples = comfy.utils.common_upscale(
                    image_samples, target_width, target_height, "bislerp", "disabled"
                )
            else:
                lanczos_samples = comfy.utils.common_upscale(
                    image_samples, target_width, target_height, "lanczos", "disabled"
                )
                bislerp_samples = comfy.utils.common_upscale(
                    image_samples, target_width, target_height, "bislerp", "disabled"
                ).to(lanczos_samples)
                scaled_samples = torch.lerp(lanczos_samples, bislerp_samples, ratio)
        else:
            scaled_samples = comfy.utils.common_upscale(
                image_samples, target_width, target_height, "lanczos", "disabled"
            )

        scaled = scaled_samples.clamp(0.0, 1.0).movedim(1, -1)

        # Anima's WanVAE decodes image latents as B,T,H,W,C even when T is 1.
        # Feeding that 5D tensor directly back into its image encoder selects
        # the temporal-video path and can leave WanVAE's internal `out`
        # uninitialized. Match the reference RES4LYF node by treating decoded
        # frames as an ordinary image batch before encoding.
        if scaled.ndim == 5:
            scaled = scaled.reshape(-1, scaled.shape[-3], scaled.shape[-2], scaled.shape[-1])

        encoded = vae.encode(scaled[..., :3]).to(source_samples)

        result = dict(latent)
        result["samples"] = encoded
        return (result,)


NODE_CLASS_MAPPINGS = {
    "easy animaLatentUpscaleWithVAEBy": LatentUpscaleWithVAEBy,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "easy animaLatentUpscaleWithVAEBy": "Latent Upscale with VAE (By)",
}
