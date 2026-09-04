# SPDX-License-Identifier: GPL-3.0-only

import math
from typing import Tuple

import numpy as np
import torch
from PIL import Image, ImageDraw


MAX_RESOLUTION = 8192


def _smooth_random_curve(
    rng: np.random.Generator,
    length: int,
    control_step: int,
    amplitude: float,
    smooth_passes: int = 2,
) -> np.ndarray:
    """Create a repeatable 1D random curve using interpolated control points."""
    control_step = max(8, int(control_step))
    xs = np.arange(0, length + control_step, control_step, dtype=np.float32)
    values = rng.uniform(-1.0, 1.0, size=len(xs)).astype(np.float32)
    values[0] *= 0.45
    values[-1] *= 0.45
    curve = np.interp(np.arange(length, dtype=np.float32), xs, values).astype(np.float32)

    # Preserve torn-paper direction changes while removing digital-looking spikes
    for _ in range(max(0, smooth_passes)):
        kernel_size = max(3, control_step // 5)
        if kernel_size % 2 == 0:
            kernel_size += 1
        kernel = np.ones(kernel_size, dtype=np.float32) / kernel_size
        curve = np.convolve(curve, kernel, mode="same")

    return curve * float(amplitude)


def _make_line_mask(
    width: int,
    height: int,
    center_y: float,
    base_thickness: float,
    roughness: float,
    rng: np.random.Generator,
    supersample: int,
) -> Image.Image:
    w = width * supersample
    h = height * supersample
    s = float(supersample)

    center = center_y * s
    thickness = max(1.0, base_thickness * s)
    rough = max(0.0, roughness * s)

    # Multi-scale path noise: large waves + medium tears + fine fibers
    coarse = _smooth_random_curve(rng, w, max(80, int(w / 8)), rough * 0.72, 1)
    medium = _smooth_random_curve(rng, w, max(28, int(w / 28)), rough * 0.24, 1)
    fine = _smooth_random_curve(rng, w, max(8, int(w / 110)), rough * 0.07, 0)
    center_curve = center + coarse + medium + fine

    thickness_wave = _smooth_random_curve(
        rng,
        w,
        max(24, int(w / 35)),
        thickness * 0.34,
        1,
    )
    thickness_curve = np.clip(thickness + thickness_wave, thickness * 0.45, thickness * 1.75)

    edge_top = _smooth_random_curve(rng, w, max(7, int(w / 150)), max(1.0, thickness * 0.13), 0)
    edge_bottom = _smooth_random_curve(rng, w, max(7, int(w / 150)), max(1.0, thickness * 0.13), 0)

    upper = center_curve - thickness_curve / 2.0 + edge_top
    lower = center_curve + thickness_curve / 2.0 + edge_bottom
    upper = np.clip(upper, 0, h - 1)
    lower = np.clip(lower, 0, h - 1)

    x = np.arange(w, dtype=np.int32)
    upper_pts = list(zip(x.tolist(), np.rint(upper).astype(np.int32).tolist()))
    lower_pts = list(zip(x[::-1].tolist(), np.rint(lower[::-1]).astype(np.int32).tolist()))

    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(upper_pts + lower_pts, fill=255)

    # Fibrous protrusions and small edge bites
    fray_count = max(12, int(w / max(18, thickness * 0.55)))
    for _ in range(fray_count):
        px = int(rng.integers(0, w))
        choose_upper = bool(rng.integers(0, 2))
        boundary = upper[px] if choose_upper else lower[px]
        radius_x = int(max(1, rng.uniform(thickness * 0.03, thickness * 0.13)))
        radius_y = int(max(1, rng.uniform(thickness * 0.02, thickness * 0.10)))
        outward = -1 if choose_upper else 1
        cy = int(np.clip(boundary + outward * rng.uniform(0.0, thickness * 0.16), 0, h - 1))
        draw.ellipse((px - radius_x, cy - radius_y, px + radius_x, cy + radius_y), fill=255)

    bite_count = max(8, fray_count // 2)
    for _ in range(bite_count):
        px = int(rng.integers(0, w))
        choose_upper = bool(rng.integers(0, 2))
        boundary = upper[px] if choose_upper else lower[px]
        radius_x = int(max(1, rng.uniform(thickness * 0.025, thickness * 0.09)))
        radius_y = int(max(1, rng.uniform(thickness * 0.02, thickness * 0.075)))
        inward = 1 if choose_upper else -1
        cy = int(np.clip(boundary + inward * rng.uniform(0.0, thickness * 0.11), 0, h - 1))
        draw.ellipse((px - radius_x, cy - radius_y, px + radius_x, cy + radius_y), fill=0)

    if supersample > 1:
        mask = mask.resize((width, height), Image.Resampling.LANCZOS)

    return mask


class TornEdgeLines:
    """Generate two random torn-paper lines on a black canvas plus a combined mask."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "width": (
                    "INT",
                    {"default": 1536, "min": 64, "max": MAX_RESOLUTION, "step": 8},
                ),
                "height": (
                    "INT",
                    {"default": 1024, "min": 64, "max": MAX_RESOLUTION, "step": 8},
                ),
                "top_y_percent": (
                    "FLOAT",
                    {"default": 27.0, "min": 0.0, "max": 100.0, "step": 0.1},
                ),
                "bottom_y_percent": (
                    "FLOAT",
                    {"default": 77.0, "min": 0.0, "max": 100.0, "step": 0.1},
                ),
                "top_thickness": (
                    "INT",
                    {"default": 34, "min": 1, "max": 1024, "step": 1},
                ),
                "bottom_thickness": (
                    "INT",
                    {"default": 42, "min": 1, "max": 1024, "step": 1},
                ),
                "roughness": (
                    "INT",
                    {"default": 90, "min": 0, "max": 1024, "step": 1},
                ),
                "seed": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 0xFFFFFFFFFFFFFFFF,
                        "control_after_generate": True,
                    },
                ),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("line_image", "line_mask")
    FUNCTION = "generate"
    CATEGORY = "EasyUse-Anima/Image"
    DESCRIPTION = "Generate two random torn-paper lines. Top and bottom thickness are independently adjustable."

    def generate(
        self,
        width: int,
        height: int,
        top_y_percent: float,
        bottom_y_percent: float,
        top_thickness: int,
        bottom_thickness: int,
        roughness: int,
        seed: int,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        width = int(width)
        height = int(height)
        rng = np.random.default_rng(int(seed) & 0xFFFFFFFFFFFFFFFF)

        # 2x antialiasing at ordinary sizes; avoid excessive RAM on very large canvases
        supersample = 2 if width * height <= 4_194_304 else 1

        top_center = np.clip(float(top_y_percent), 0.0, 100.0) * (height - 1) / 100.0
        bottom_center = np.clip(float(bottom_y_percent), 0.0, 100.0) * (height - 1) / 100.0

        top_rng = np.random.default_rng(rng.integers(0, 0xFFFFFFFFFFFFFFFF, dtype=np.uint64))
        bottom_rng = np.random.default_rng(rng.integers(0, 0xFFFFFFFFFFFFFFFF, dtype=np.uint64))

        top_mask = _make_line_mask(
            width,
            height,
            top_center,
            float(top_thickness),
            float(roughness),
            top_rng,
            supersample,
        )
        bottom_mask = _make_line_mask(
            width,
            height,
            bottom_center,
            float(bottom_thickness),
            float(roughness),
            bottom_rng,
            supersample,
        )

        top_np = np.asarray(top_mask, dtype=np.float32) / 255.0
        bottom_np = np.asarray(bottom_mask, dtype=np.float32) / 255.0
        combined = np.maximum(top_np, bottom_np).astype(np.float32)

        # Reference style: white torn lines on black
        image_np = np.repeat(combined[..., None], 3, axis=2)
        image = torch.from_numpy(image_np).unsqueeze(0)
        mask = torch.from_numpy(combined).unsqueeze(0)
        return image, mask


NODE_CLASS_MAPPINGS = {
    "TornEdgeLines": TornEdgeLines,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TornEdgeLines": "Torn Edge Lines / 破れ線ランダム生成",
}
