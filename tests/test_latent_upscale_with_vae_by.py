import importlib.util
import sys
import types
import unittest
from pathlib import Path

import torch


class _ComfyUtils(types.ModuleType):
    calls = []

    def common_upscale(self, image, width, height, upscale_method, crop):
        type(self).calls.append(
            (tuple(image.shape), width, height, upscale_method, crop)
        )
        value = 0.8 if upscale_method == "bislerp" else 0.2
        return torch.full(image.shape[:-2] + (height, width), value)


class _FakeVAE:
    def __init__(self):
        self.encoded_shape = None
        self.encoded_mean = None

    def decode(self, samples):
        batch = samples.shape[0]
        return torch.zeros(batch, 5, 32, 48, 4)

    def encode(self, image):
        self.encoded_shape = tuple(image.shape)
        self.encoded_mean = image.mean().item()
        batch, height, width, _channels = image.shape
        return torch.ones(batch, 16, max(1, height // 8), max(1, width // 8))


class LatentUpscaleWithVAEByTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        comfy = types.ModuleType("comfy")
        comfy.__path__ = []
        comfy_utils = _ComfyUtils("comfy.utils")
        comfy.utils = comfy_utils
        sys.modules["comfy"] = comfy
        sys.modules["comfy.utils"] = comfy_utils

        module_path = Path(__file__).parents[1] / "latent_upscale_with_vae_by.py"
        spec = importlib.util.spec_from_file_location(
            "latent_upscale_with_vae_by_test", module_path
        )
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_exposes_single_factor_based_latent_node(self):
        node = self.module.LatentUpscaleWithVAEBy
        required = node.INPUT_TYPES()["required"]
        self.assertEqual(
            set(required),
            {"latent", "vae", "scale_by", "upscale_method", "bislerp_ratio"},
        )
        self.assertEqual(required["scale_by"][1]["default"], 1.25)
        self.assertEqual(required["upscale_method"][1]["default"], "lanczos")
        self.assertEqual(required["upscale_method"][0], ("lanczos", "bislerp"))
        self.assertEqual(required["bislerp_ratio"][1]["default"], 0.50)
        self.assertEqual(required["bislerp_ratio"][1]["step"], 0.01)
        self.assertEqual(required["bislerp_ratio"][1]["round"], 0.01)
        self.assertEqual(node.RETURN_TYPES, ("LATENT",))

    def test_decodes_scales_and_reencodes_without_mutating_input(self):
        source_samples = torch.zeros(1, 16, 2, 3, dtype=torch.float16)
        latent = {"samples": source_samples, "batch_index": [7]}
        vae = _FakeVAE()
        _ComfyUtils.calls = []

        result = self.module.LatentUpscaleWithVAEBy().upscale(
            latent=latent,
            vae=vae,
            scale_by=1.25,
            upscale_method="lanczos",
        )[0]

        self.assertIsNot(result, latent)
        self.assertIs(result["batch_index"], latent["batch_index"])
        self.assertIs(latent["samples"], source_samples)
        self.assertEqual(
            _ComfyUtils.calls,
            [((1, 4, 5, 32, 48), 60, 40, "lanczos", "disabled")],
        )
        self.assertEqual(vae.encoded_shape, (5, 40, 60, 3))
        self.assertEqual(tuple(result["samples"].shape), (5, 16, 5, 7))
        self.assertEqual(result["samples"].dtype, source_samples.dtype)

    def test_bislerp_ratio_blends_from_lanczos_to_bislerp(self):
        source_samples = torch.zeros(1, 16, 2, 3)
        vae = _FakeVAE()
        _ComfyUtils.calls = []

        self.module.LatentUpscaleWithVAEBy().upscale(
            latent={"samples": source_samples},
            vae=vae,
            scale_by=1.25,
            upscale_method="bislerp",
            bislerp_ratio=0.25,
        )

        self.assertEqual(
            [call[3] for call in _ComfyUtils.calls],
            ["lanczos", "bislerp"],
        )
        self.assertAlmostEqual(vae.encoded_mean, 0.35, places=5)

    def test_bislerp_ratio_is_clamped_and_rounded_to_two_decimals(self):
        source_samples = torch.zeros(1, 16, 2, 3)
        vae = _FakeVAE()
        _ComfyUtils.calls = []

        self.module.LatentUpscaleWithVAEBy().upscale(
            latent={"samples": source_samples},
            vae=vae,
            scale_by=1.25,
            upscale_method="bislerp",
            bislerp_ratio=1.234,
        )

        self.assertEqual([call[3] for call in _ComfyUtils.calls], ["bislerp"])
        self.assertAlmostEqual(vae.encoded_mean, 0.8, places=5)

    def test_rejects_invalid_latent_dictionary(self):
        with self.assertRaisesRegex(ValueError, "samples"):
            self.module.LatentUpscaleWithVAEBy().upscale(
                latent={},
                vae=_FakeVAE(),
                scale_by=1.25,
                upscale_method="lanczos",
            )


if __name__ == "__main__":
    unittest.main()
