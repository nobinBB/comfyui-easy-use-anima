import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
from safetensors.numpy import save_file


class _Config:
    unet_config = {"image_model": "anima"}


class _Model:
    def __init__(self):
        self.model = types.SimpleNamespace(model_config=_Config())


class _AnimaTokenizer:
    def __init__(self):
        self.qwen3_06b = object()


class _Clip:
    def __init__(self):
        self.tokenizer = _AnimaTokenizer()


class _Vae:
    latent_channels = 16


class AnimaLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.model_root = Path(cls.temp_dir.name)
        cls.anima_name = "renamed/custom_model.safetensors"
        cls.fake_anima_name = "Anima/not_anima.safetensors"
        cls.krea_name = "krea2.safetensors"
        cls.broken_name = "broken.safetensors"

        for name in (
            cls.anima_name,
            cls.fake_anima_name,
            cls.krea_name,
            cls.broken_name,
        ):
            (cls.model_root / name).parent.mkdir(parents=True, exist_ok=True)

        save_file(
            {
                "model.diffusion_model.blocks.0.mlp.layer1.weight": np.zeros(
                    (1,), dtype=np.float32
                ),
                "model.diffusion_model.llm_adapter.blocks.0.cross_attn.q_proj.weight": np.zeros(
                    (1,), dtype=np.float32
                ),
            },
            cls.model_root / cls.anima_name,
        )
        save_file(
            {
                "blocks.0.mlp.layer1.weight": np.zeros((1,), dtype=np.float32),
                "other.llm_adapter.blocks.0.cross_attn.q_proj.weight": np.zeros(
                    (1,), dtype=np.float32
                ),
            },
            cls.model_root / cls.fake_anima_name,
        )
        save_file(
            {"transformer_blocks.0.attn.weight": np.zeros((1,), dtype=np.float32)},
            cls.model_root / cls.krea_name,
        )
        (cls.model_root / cls.broken_name).write_bytes(b"not-safetensors")

        folder_paths = types.ModuleType("folder_paths")
        files = {
            "diffusion_models": [
                cls.anima_name,
                cls.fake_anima_name,
                cls.krea_name,
                cls.broken_name,
            ],
            "text_encoders": ["qwen.safetensors"],
            "vae": ["qwen_vae.safetensors"],
        }
        folder_paths.get_filename_list = lambda kind: files.get(kind, [])
        folder_paths.get_full_path = lambda kind, name: str(cls.model_root / name)

        class UNETLoader:
            def load_unet(self, name, dtype):
                return (_Model(),)

        class CLIPLoader:
            def load_clip(self, name, type, device):
                self.args = name, type, device
                return (_Clip(),)

        class VAELoader:
            def load_vae(self, name):
                return (_Vae(),)

        class EmptyLatentImage:
            def generate(self, width, height, batch_size):
                return ({"samples": (width, height, batch_size)},)

        nodes = types.ModuleType("nodes")
        nodes.MAX_RESOLUTION = 16384
        nodes.NODE_CLASS_MAPPINGS = {
            "UNETLoader": UNETLoader,
            "CLIPLoader": CLIPLoader,
            "VAELoader": VAELoader,
            "EmptyLatentImage": EmptyLatentImage,
        }
        sys.modules["folder_paths"] = folder_paths
        sys.modules["nodes"] = nodes

        module_path = Path(__file__).parents[1] / "anima_loader.py"
        sys.path.insert(0, str(module_path.parent))
        sys.modules.pop("anima_model_filter", None)
        spec = importlib.util.spec_from_file_location("easy_use_anima_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_has_no_sd_checkpoint_or_clip_override_inputs(self):
        inputs = self.module.EasyAnimaFullLoader.INPUT_TYPES()
        all_inputs = set(inputs["required"]) | set(inputs.get("optional", {}))
        self.assertNotIn("ckpt_name", all_inputs)
        self.assertNotIn("clip_override", all_inputs)
        self.assertNotIn("clip_skip", all_inputs)
        self.assertNotIn("lora_clip_strength", all_inputs)
        self.assertNotIn("lora_name", all_inputs)
        self.assertNotIn("lora_model_strength", all_inputs)
        self.assertNotIn("optional_lora_stack", all_inputs)
        self.assertNotIn("positive", all_inputs)
        self.assertNotIn("negative", all_inputs)

    def test_builds_easy_pipe(self):
        result = self.module.EasyAnimaFullLoader().load_anima(
            model_name=self.anima_name,
            weight_dtype="default",
            clip_name="qwen.safetensors",
            clip_device="default",
            vae_name="qwen_vae.safetensors",
            resolution="896 x 1152",
            empty_latent_width=1024,
            empty_latent_height=1024,
            batch_size=2,
        )

        pipe, model, vae, clip, latent, model_name, vae_name = result
        self.assertEqual(vae.latent_channels, 16)
        self.assertIs(pipe["clip"], clip)
        self.assertIsNone(pipe["positive"])
        self.assertIsNone(pipe["negative"])
        self.assertEqual(latent["samples"], (896, 1152, 2))
        self.assertEqual(model_name, self.anima_name)
        self.assertEqual(vae_name, "qwen_vae.safetensors")
        self.assertEqual(pipe["loader_settings"]["model_family"], "anima")

    def test_rejects_non_anima_model(self):
        bad_model = types.SimpleNamespace(
            model=types.SimpleNamespace(
                model_config=types.SimpleNamespace(unet_config={"image_model": "sdxl"})
            )
        )
        with self.assertRaisesRegex(RuntimeError, "not detected as an Anima"):
            self.module._assert_anima_model(bad_model, "sdxl.safetensors")

    def test_rejects_non_anima_clip(self):
        bad_clip = types.SimpleNamespace(tokenizer=types.SimpleNamespace())
        with self.assertRaisesRegex(RuntimeError, "Anima Qwen3 0.6B"):
            self.module._assert_anima_clip(bad_clip, "clip_l.safetensors")

    def test_rejects_four_channel_sd_vae(self):
        bad_vae = types.SimpleNamespace(latent_channels=4)
        with self.assertRaisesRegex(RuntimeError, "expected a 16-channel"):
            self.module._assert_anima_vae(bad_vae, "sd_vae.safetensors")

    def test_prefers_qwen_vae_as_default(self):
        inputs = self.module.EasyAnimaFullLoader.INPUT_TYPES()["required"]
        vae_names, vae_options = inputs["vae_name"]
        self.assertEqual(vae_names[0], "qwen_vae.safetensors")
        self.assertEqual(vae_options["default"], "qwen_vae.safetensors")

    def test_custom_resolution_is_kept(self):
        self.assertEqual(
            self.module._resolve_size(self.module.CUSTOM_RESOLUTION, 1000, 1200),
            (1000, 1200),
        )

    def test_resolutions_match_easy_use_base_list(self):
        resolutions = self.module.ANIMA_RESOLUTIONS
        self.assertEqual(len(resolutions), 31)
        self.assertEqual(resolutions[0], self.module.CUSTOM_RESOLUTION)
        self.assertIn("512 x 512", resolutions)
        self.assertIn("816 x 1920", resolutions)
        self.assertIn("1536 x 640", resolutions)
        self.assertIn("2560 x 1440", resolutions)

    def test_uses_new_node_id_to_avoid_stale_widget_layout(self):
        self.assertIn("easy animaLoaderV2", self.module.NODE_CLASS_MAPPINGS)
        self.assertNotIn("easy animaLoader", self.module.NODE_CLASS_MAPPINGS)
        self.assertNotIn("easy animaFullLoader", self.module.NODE_CLASS_MAPPINGS)

    def test_has_no_prompt_conditioning_output_slots(self):
        self.assertNotIn("positive", self.module.EasyAnimaFullLoader.RETURN_NAMES)
        self.assertNotIn("negative", self.module.EasyAnimaFullLoader.RETURN_NAMES)
        self.assertNotIn("CONDITIONING", self.module.EasyAnimaFullLoader.RETURN_TYPES)

    def test_outputs_model_and_vae_names_as_combo_types(self):
        output_types = self.module.EasyAnimaFullLoader.RETURN_TYPES
        output_names = self.module.EasyAnimaFullLoader.RETURN_NAMES
        model_index = output_names.index("model_name")
        vae_index = output_names.index("vae_name")
        self.assertIsInstance(output_types[model_index], list)
        self.assertIsInstance(output_types[vae_index], list)
        self.assertIn(self.anima_name, output_types[model_index])
        self.assertNotIn(self.fake_anima_name, output_types[model_index])
        self.assertNotIn(self.krea_name, output_types[model_index])
        self.assertNotIn(self.broken_name, output_types[model_index])
        self.assertIn("qwen_vae.safetensors", output_types[vae_index])

    def test_model_combo_detects_architecture_not_path_or_filename(self):
        model_names = self.module.EasyAnimaFullLoader.INPUT_TYPES()["required"][
            "model_name"
        ][0]
        self.assertEqual(model_names, [self.anima_name])


if __name__ == "__main__":
    unittest.main()
