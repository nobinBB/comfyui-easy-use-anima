import importlib.util
import math
import unittest
from unittest import mock
from pathlib import Path


class DynamicTextHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_path = Path(__file__).parents[1] / "dynamic_text_hub.py"
        spec = importlib.util.spec_from_file_location("dynamic_text_hub_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_exposes_combined_and_twenty_individual_outputs(self):
        node = self.module.DynamicTextHub
        self.assertEqual(len(node.RETURN_TYPES), 21)
        self.assertEqual(node.RETURN_NAMES[0], "text_all")
        self.assertEqual(node.RETURN_NAMES[1], "text_1")
        self.assertEqual(node.RETURN_NAMES[-1], "text_20")

    def test_combines_only_active_text_fields(self):
        result = self.module.DynamicTextHub().combine(
            count=3,
            text_1="first",
            text_2="second",
            text_3="third",
            text_4="hidden",
        )
        self.assertEqual(result[0], "first\nsecond\nthird")
        self.assertEqual(result[1:5], ("first", "second", "third", "hidden"))

    def test_joins_active_fields_with_custom_delimiter(self):
        result = self.module.DynamicTextHub().combine(
            count=3,
            mode="join_with_delimiter",
            delimiter=" | ",
            text_1="first",
            text_2="second",
            text_3="third",
            text_4="hidden",
        )
        self.assertEqual(result[0], "first | second | third")

    def test_line_by_line_ignores_delimiter(self):
        result = self.module.DynamicTextHub().combine(
            count=2,
            mode="line_by_line",
            delimiter="ignored",
            text_1="first",
            text_2="second",
        )
        self.assertEqual(result[0], "first\nsecond")

    def test_choice_group_automatically_selects_one_option(self):
        with mock.patch.object(
            self.module.random, "choice", side_effect=lambda options: options[1]
        ):
            result = self.module.DynamicTextHub().combine(
                count=1,
                mode="line_by_line",
                text_1="portrait, {red hair|green eyes|black dress}",
            )
        self.assertEqual(result[0], "portrait, green eyes")
        self.assertEqual(result[1], "portrait, green eyes")

    def test_choice_groups_work_with_delimiter_mode(self):
        with mock.patch.object(
            self.module.random, "choice", side_effect=lambda options: options[-1]
        ):
            result = self.module.DynamicTextHub().combine(
                count=2,
                mode="join_with_delimiter",
                delimiter=" / ",
                text_1="{red|blue} hair",
                text_2="{dress|jacket}",
            )
        self.assertEqual(result[0], "blue hair / jacket")
        self.assertEqual(result[1:3], ("blue hair", "jacket"))

    def test_braces_without_pipe_are_preserved(self):
        result = self.module.DynamicTextHub().combine(
            count=1,
            text_1="plain {unchanged} text",
        )
        self.assertEqual(result[0], "plain {unchanged} text")
        self.assertEqual(result[1], "plain {unchanged} text")

    def test_choice_groups_force_execution_each_queue(self):
        self.assertTrue(math.isnan(self.module.DynamicTextHub.IS_CHANGED()))

    def test_clean_whitespace_applies_to_combined_and_individual_outputs(self):
        result = self.module.DynamicTextHub().combine(
            count=2,
            mode="join_with_delimiter",
            delimiter=", ",
            clean_whitespace=True,
            text_1="  first   value  ",
            text_2="second\n\tvalue",
        )
        self.assertEqual(result[0], "first value, second value")
        self.assertEqual(result[1:3], ("first value", "second value"))

    def test_clean_whitespace_false_preserves_text(self):
        result = self.module.DynamicTextHub().combine(
            count=1,
            clean_whitespace=False,
            text_1="  keep   spacing  ",
        )
        self.assertEqual(result[0], "  keep   spacing  ")
        self.assertEqual(result[1], "  keep   spacing  ")

    def test_clamps_count_to_supported_range(self):
        low = self.module.DynamicTextHub().combine(count=0, text_1="one")
        high = self.module.DynamicTextHub().combine(
            count=999, **{f"text_{index}": str(index) for index in range(1, 21)}
        )
        self.assertEqual(low[0], "one")
        self.assertEqual(high[0].splitlines(), [str(index) for index in range(1, 21)])

    def test_count_widget_matches_frontend_limit(self):
        optional = self.module.DynamicTextHub.INPUT_TYPES()["optional"]
        count_spec = optional["count"]
        self.assertEqual(count_spec[1]["min"], 1)
        self.assertEqual(count_spec[1]["max"], 20)
        self.assertEqual(optional["mode"][0], self.module.JOIN_MODES)
        self.assertEqual(optional["mode"][0], ("line_by_line", "join_with_delimiter"))
        self.assertFalse(optional["clean_whitespace"][1]["default"])

    def test_frontend_does_not_reorder_dynamic_input_slots(self):
        frontend_path = Path(__file__).parents[1] / "web" / "dynamic_text_hub.js"
        frontend = frontend_path.read_text(encoding="utf-8")
        self.assertIn("node.addInput(name, type, options)", frontend)
        self.assertIn("node.removeInput(inputIndex)", frontend)
        self.assertNotIn("node.inputs.splice", frontend)


if __name__ == "__main__":
    unittest.main()
