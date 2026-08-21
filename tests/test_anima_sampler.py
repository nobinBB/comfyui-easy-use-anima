import importlib.util
import sys
import types
import unittest
from pathlib import Path


class _BaseEasyFullKSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pipe": ("PIPE_LINE",),
                "steps": ("INT",),
                "cfg": ("FLOAT",),
                "sampler_name": (["euler", "custom_sampler"],),
                "scheduler": (["normal", "custom_scheduler"],),
                "denoise": ("FLOAT",),
                "image_output": (["Preview", "Hide"],),
                "link_id": ("INT",),
                "save_prefix": ("STRING",),
            },
            "optional": {"model": ("MODEL",)},
        }

    def run(self, pipe, sampler_name, scheduler, **kwargs):
        # Reproduce the upstream bug: the model override is used for sampling,
        # but the output pipe keeps the original pipe model.
        output_pipe = {
            **pipe,
            "loader_settings": {
                **pipe.get("loader_settings", {}),
                "sampler_name": sampler_name,
                "scheduler": scheduler,
            },
        }
        return {
            "ui": {"images": []},
            "result": (
                output_pipe,
                "image",
                output_pipe["model"],
                "positive",
                "negative",
                "latent",
                "vae",
                "clip",
                123,
            ),
        }


class AnimaSamplerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        comfy = types.ModuleType("comfy")
        comfy.__path__ = []
        samplers = types.ModuleType("comfy.samplers")

        class KSampler:
            SAMPLERS = ["euler", "custom_sampler"]
            SCHEDULERS = ["normal", "custom_scheduler"]

        samplers.KSampler = KSampler
        comfy.samplers = samplers

        nodes = types.ModuleType("nodes")
        nodes.NODE_CLASS_MAPPINGS = {
            "easy fullkSampler": _BaseEasyFullKSampler,
        }

        sys.modules["comfy"] = comfy
        sys.modules["comfy.samplers"] = samplers
        sys.modules["nodes"] = nodes

        module_path = Path(__file__).parents[1] / "anima_sampler.py"
        spec = importlib.util.spec_from_file_location("anima_sampler_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def _run(self, model=None):
        pipe = {
            "model": "base-model",
            "loader_settings": {"model_family": "anima"},
        }
        kwargs = {"model": model} if model is not None else {}
        return self.module.AnimaFullKSampler().run(
            pipe=pipe,
            steps=30,
            cfg=4.5,
            sampler_name="custom_sampler",
            scheduler="custom_scheduler",
            denoise=1.0,
            image_output="Preview",
            link_id=0,
            save_prefix="ComfyUI",
            **kwargs,
        )

    def test_propagates_override_model_to_pipe_and_model_output(self):
        result = self._run(model="lora-patched-anima-model")
        outputs = result["result"]
        self.assertEqual(outputs[0]["model"], "lora-patched-anima-model")
        self.assertEqual(outputs[2], "lora-patched-anima-model")

    def test_preserves_pipe_model_without_override(self):
        result = self._run()
        outputs = result["result"]
        self.assertEqual(outputs[0]["model"], "base-model")
        self.assertEqual(outputs[2], "base-model")

    def test_outputs_sampler_and_scheduler_as_combo_types(self):
        output_types = self.module.AnimaFullKSampler.RETURN_TYPES
        output_names = self.module.AnimaFullKSampler.RETURN_NAMES
        sampler_index = output_names.index("sampler_name")
        scheduler_index = output_names.index("scheduler")
        self.assertIsInstance(output_types[sampler_index], list)
        self.assertIsInstance(output_types[scheduler_index], list)
        self.assertIn("custom_sampler", output_types[sampler_index])
        self.assertIn("custom_scheduler", output_types[scheduler_index])
        self.assertIs(output_types[sampler_index], self.module.comfy.samplers.KSampler.SAMPLERS)
        self.assertIs(output_types[scheduler_index], self.module.comfy.samplers.KSampler.SCHEDULERS)

        # Extensions commonly add choices after this node was imported.  The
        # output COMBO must see those late additions just like standard KSampler.
        self.module.comfy.samplers.KSampler.SAMPLERS.append("late_sampler")
        self.module.comfy.samplers.KSampler.SCHEDULERS.append("late_scheduler")
        self.assertIn("late_sampler", output_types[sampler_index])
        self.assertIn("late_scheduler", output_types[scheduler_index])

        replacement_samplers = ["replacement_sampler"]
        replacement_schedulers = ["replacement_scheduler"]
        self.module.comfy.samplers.KSampler.SAMPLERS = replacement_samplers
        self.module.comfy.samplers.KSampler.SCHEDULERS = replacement_schedulers
        refreshed_types = self.module.AnimaFullKSampler.RETURN_TYPES
        self.assertIs(refreshed_types[sampler_index], replacement_samplers)
        self.assertIs(refreshed_types[scheduler_index], replacement_schedulers)

        outputs = self._run()["result"]
        self.assertEqual(outputs[sampler_index], "custom_sampler")
        self.assertEqual(outputs[scheduler_index], "custom_scheduler")
        self.assertEqual(
            outputs[0]["loader_settings"]["sampler_name"], "custom_sampler"
        )
        self.assertEqual(
            outputs[0]["loader_settings"]["scheduler"], "custom_scheduler"
        )

    def test_uses_easy_full_ksampler_inputs(self):
        self.assertEqual(
            self.module.AnimaFullKSampler.INPUT_TYPES(),
            _BaseEasyFullKSampler.INPUT_TYPES(),
        )

    def test_runs_without_easy_use(self):
        nodes_module = self.module.nodes
        base = nodes_module.NODE_CLASS_MAPPINGS.pop("easy fullkSampler")
        captured = {}

        def common_ksampler(
            model,
            seed,
            steps,
            cfg,
            sampler_name,
            scheduler,
            positive,
            negative,
            latent,
            denoise=1.0,
        ):
            captured.update(
                model=model,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler_name=sampler_name,
                scheduler=scheduler,
                positive=positive,
                negative=negative,
                latent=latent,
                denoise=denoise,
            )
            return ({"samples": "sampled-latent"},)

        nodes_module.common_ksampler = common_ksampler
        try:
            inputs = self.module.AnimaFullKSampler.INPUT_TYPES()
            self.assertNotIn("xyPlot", inputs["optional"])

            pipe = {
                "model": "anima-model",
                "positive": "positive-conditioning",
                "negative": "negative-conditioning",
                "samples": {"samples": "empty-latent"},
                "vae": "anima-vae",
                "clip": "anima-clip",
                "seed": 42,
                "loader_settings": {"model_family": "anima"},
            }
            result = self.module.AnimaFullKSampler().run(
                pipe=pipe,
                steps=25,
                cfg=5.0,
                sampler_name="custom_sampler",
                scheduler="custom_scheduler",
                denoise=0.9,
                image_output="None",
                link_id=0,
                save_prefix="ComfyUI",
            )
        finally:
            nodes_module.NODE_CLASS_MAPPINGS["easy fullkSampler"] = base

        outputs = result["result"]
        self.assertEqual(outputs[0]["model"], "anima-model")
        self.assertEqual(outputs[0]["samples"], {"samples": "sampled-latent"})
        self.assertEqual(outputs[2], "anima-model")
        self.assertEqual(outputs[5], {"samples": "sampled-latent"})
        self.assertEqual(outputs[8], 42)
        self.assertEqual(outputs[9], "custom_sampler")
        self.assertEqual(outputs[10], "custom_scheduler")
        self.assertEqual(captured["model"], "anima-model")
        self.assertEqual(captured["positive"], "positive-conditioning")
        self.assertEqual(captured["negative"], "negative-conditioning")


if __name__ == "__main__":
    unittest.main()
