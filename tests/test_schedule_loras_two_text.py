import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


class ScheduleLorasTwoTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_path = Path(__file__).parents[1] / "schedule_loras_two_text.py"
        spec = importlib.util.spec_from_file_location(
            "schedule_loras_two_text_test", module_path
        )
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_exposes_two_multiline_text_boxes_and_text_output(self):
        inputs = self.module.ScheduleLorasTwoText.INPUT_TYPES()["optional"]
        self.assertTrue(inputs["text_1"][1]["multiline"])
        self.assertTrue(inputs["text_2"][1]["multiline"])
        self.assertEqual(
            self.module.ScheduleLorasTwoText.RETURN_NAMES,
            ("model", "clip", "loras_text", "text"),
        )

    def test_combines_non_empty_boxes_with_newline(self):
        self.assertEqual(self.module._combine_text("first", "second"), "first\nsecond")
        self.assertEqual(self.module._combine_text("first", ""), "first")
        self.assertEqual(self.module._combine_text("", "second"), "second")

    def test_delegates_to_prompt_control_and_returns_combined_text(self):
        calls = []

        class FakePromptControlNode:
            def apply(self, **kwargs):
                calls.append(kwargs)
                return {
                    "result": ("scheduled-model", "scheduled-clip"),
                    "expand": {"nodes": []},
                }

        fake_nodes = types.SimpleNamespace(
            NODE_CLASS_MAPPINGS={"PCLazyLoraLoader": FakePromptControlNode}
        )
        with mock.patch.dict(sys.modules, {"nodes": fake_nodes}):
            result = self.module.ScheduleLorasTwoText().apply(
                unique_id="42",
                model="model",
                clip="clip",
                text_1="portrait",
                text_2="<lora:style:0.8>",
            )

        self.assertEqual(calls[0]["text"], "portrait\n<lora:style:0.8>")
        self.assertEqual(
            result["result"],
            (
                "scheduled-model",
                "scheduled-clip",
                "portrait",
                "portrait\n<lora:style:0.8>",
            ),
        )
        self.assertEqual(result["expand"], {"nodes": []})

    def test_reports_missing_prompt_control(self):
        fake_nodes = types.SimpleNamespace(NODE_CLASS_MAPPINGS={})
        with mock.patch.dict(sys.modules, {"nodes": fake_nodes}):
            with self.assertRaisesRegex(RuntimeError, "requires comfyui-prompt-control"):
                self.module.ScheduleLorasTwoText().apply(unique_id="42")


if __name__ == "__main__":
    unittest.main()
