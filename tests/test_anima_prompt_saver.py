import hashlib
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

import numpy as np
from PIL import Image
from safetensors.numpy import save_file


class _ImageTensor:
    def __init__(self):
        self.shape = (2, 3, 3)

    def cpu(self):
        return self

    def numpy(self):
        return np.zeros(self.shape, dtype=np.float32)


class AnimaPromptSaverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.output_dir = Path(cls.temp_dir.name)
        cls.model_root = cls.output_dir / "models"
        cls.anima_name = "anything/renamed.safetensors"
        cls.fake_anima_name = "Anima/not_anima.safetensors"
        cls.krea_name = "krea2.safetensors"
        for name in (cls.anima_name, cls.fake_anima_name, cls.krea_name):
            (cls.model_root / name).parent.mkdir(parents=True, exist_ok=True)
        save_file(
            {
                "net.blocks.0.mlp.layer1.weight": np.zeros((1,), dtype=np.float32),
                "net.llm_adapter.blocks.0.cross_attn.q_proj.weight": np.zeros(
                    (1,), dtype=np.float32
                ),
            },
            cls.model_root / cls.anima_name,
        )
        save_file(
            {"unrelated.weight": np.zeros((1,), dtype=np.float32)},
            cls.model_root / cls.fake_anima_name,
        )
        save_file(
            {"transformer.weight": np.zeros((1,), dtype=np.float32)},
            cls.model_root / cls.krea_name,
        )
        cls.requested_folder_types = []

        folder_paths = types.ModuleType("folder_paths")

        def get_filename_list(kind):
            return {
                "diffusion_models": [
                    cls.anima_name,
                    cls.fake_anima_name,
                    cls.krea_name,
                ],
                "checkpoints": ["sdxl.safetensors"],
                "vae": ["qwen_image_vae.safetensors"],
                "embeddings": [],
            }.get(kind, [])

        def get_full_path(kind, name):
            cls.requested_folder_types.append(kind)
            return str(cls.model_root / name)

        folder_paths.get_filename_list = get_filename_list
        folder_paths.get_full_path = get_full_path
        folder_paths.get_output_directory = lambda: str(cls.output_dir)
        folder_paths.get_save_image_path = lambda *args: (
            str(cls.output_dir),
            "",
            1,
            "",
            "",
        )

        nodes = types.ModuleType("nodes")
        nodes.MAX_RESOLUTION = 16384

        comfy = types.ModuleType("comfy")
        comfy.__path__ = []
        samplers = types.ModuleType("comfy.samplers")

        class KSampler:
            SAMPLERS = ["euler", "extension_sampler"]
            SCHEDULERS = ["normal", "extension_scheduler"]

        samplers.KSampler = KSampler
        comfy.samplers = samplers

        cli_args = types.ModuleType("comfy.cli_args")
        cli_args.args = types.SimpleNamespace(disable_metadata=False)

        sys.modules["folder_paths"] = folder_paths
        sys.modules["nodes"] = nodes
        sys.modules["comfy"] = comfy
        sys.modules["comfy.samplers"] = samplers
        sys.modules["comfy.cli_args"] = cli_args

        module_path = Path(__file__).parents[1] / "anima_prompt_saver.py"
        sys.path.insert(0, str(module_path.parent))
        sys.modules.pop("anima_model_filter", None)
        spec = importlib.util.spec_from_file_location("anima_prompt_saver_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_uses_diffusion_models_and_core_ksampler_lists(self):
        inputs = self.module.AnimaPromptSaver.INPUT_TYPES()["optional"]
        self.assertEqual(inputs["model_name"][0], [self.anima_name])
        self.assertNotIn("sdxl.safetensors", inputs["model_name"][0])
        self.assertNotIn(self.fake_anima_name, inputs["model_name"][0])
        self.assertNotIn(self.krea_name, inputs["model_name"][0])
        self.assertEqual(
            inputs["sampler_name"][0], ["euler", "extension_sampler"]
        )
        self.assertEqual(
            inputs["scheduler"][0], ["normal", "extension_scheduler"]
        )

    def test_model_hash_resolves_from_diffusion_models(self):
        self.module.AnimaPromptSaver.model_hash_dict.clear()
        self.requested_folder_types.clear()
        result = self.module.AnimaPromptSaver.calculate_hash(
            self.anima_name, "model"
        )
        expected = hashlib.sha256(
            (self.model_root / self.anima_name).read_bytes()
        ).hexdigest()[:10]
        self.assertEqual(result, expected)
        self.assertEqual(self.requested_folder_types, ["diffusion_models"])

    def test_saves_png_with_anima_metadata(self):
        saver = self.module.AnimaPromptSaver()
        result = saver.save_images(
            [_ImageTensor()],
            filename="anima_test",
            path="",
            model_name=self.anima_name,
            vae_name="qwen_image_vae.safetensors",
            seed=123,
            steps=30,
            cfg=4.5,
            sampler_name="extension_sampler",
            scheduler="extension_scheduler",
            width=3,
            height=2,
            positive="anime portrait",
            negative="low quality",
            extension="png",
            calculate_hash=False,
        )

        file_path = Path(result["result"][1])
        self.assertTrue(file_path.is_file())
        with Image.open(file_path) as image:
            parameters = image.info["parameters"]
        self.assertIn("anime portrait", parameters)
        self.assertIn("Negative prompt: low quality", parameters)
        self.assertIn("Model: renamed", parameters)
        self.assertIn(
            "Sampler: extension_sampler_extension_scheduler", parameters
        )

    def test_node_is_named_anima_prompt_saver(self):
        self.assertEqual(
            self.module.NODE_DISPLAY_NAME_MAPPINGS["easy animaPromptSaver"],
            "Anima Prompt Saver",
        )


if __name__ == "__main__":
    unittest.main()
