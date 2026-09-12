import importlib.util
import unittest
from pathlib import Path


class NegativeWildcardProcessorPlusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_path = (
            Path(__file__).parents[1] / "negative_wildcard_processor_plus.py"
        )
        spec = importlib.util.spec_from_file_location(
            "negative_wildcard_processor_plus_test", module_path
        )
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_moves_only_marked_text_and_preserves_lora_tag(self):
        result = self.module.NegativeWildcardProcessorPlus().process_negative_wildcards(
            "portrait, <lora:detail:0.8>, <!bad hands!>",
            "low quality",
        )
        self.assertEqual(result[0], "portrait, <lora:detail:0.8>, ")
        self.assertEqual(result[1], "low quality bad hands")

    def test_preserves_all_unrelated_angle_bracket_tags(self):
        positive = "<lora:style:1.0>, <embedding:easynegative>, <custom:value>"
        result = self.module.NegativeWildcardProcessorPlus().process_negative_wildcards(
            positive, ""
        )
        self.assertEqual(result, (positive, ""))

    def test_supports_multiline_marked_text(self):
        result = self.module.NegativeWildcardProcessorPlus().process_negative_wildcards(
            "portrait, <!bad hands\nextra fingers!>",
            "low quality",
        )
        self.assertEqual(result[0], "portrait, ")
        self.assertEqual(result[1], "low quality bad hands\nextra fingers")

    def test_moves_multiple_blocks_in_order(self):
        result = self.module.NegativeWildcardProcessorPlus().process_negative_wildcards(
            "subject <!first!>, background <!second!>",
            "base",
        )
        self.assertEqual(result[0], "subject , background ")
        self.assertEqual(result[1], "base first second")

    def test_leaves_unclosed_marker_unchanged(self):
        positive = "portrait, <!not closed"
        result = self.module.NegativeWildcardProcessorPlus().process_negative_wildcards(
            positive, "negative"
        )
        self.assertEqual(result, (positive, "negative"))


if __name__ == "__main__":
    unittest.main()
