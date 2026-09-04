import importlib.util
import unittest
from pathlib import Path

import torch


class TornEdgeLinesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_path = Path(__file__).parents[1] / "torn_edge_lines.py"
        spec = importlib.util.spec_from_file_location("torn_edge_lines_test", module_path)
        cls.module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cls.module)

    def test_node_registration_keeps_workflow_compatible_id(self):
        self.assertIs(
            self.module.NODE_CLASS_MAPPINGS["TornEdgeLines"],
            self.module.TornEdgeLines,
        )
        self.assertEqual(
            self.module.NODE_DISPLAY_NAME_MAPPINGS["TornEdgeLines"],
            "Torn Edge Lines / 破れ線ランダム生成",
        )

    def test_generates_expected_image_and_mask_shapes(self):
        image, mask = self.module.TornEdgeLines().generate(
            width=128,
            height=96,
            top_y_percent=27.0,
            bottom_y_percent=77.0,
            top_thickness=8,
            bottom_thickness=10,
            roughness=12,
            seed=123,
        )
        self.assertEqual(tuple(image.shape), (1, 96, 128, 3))
        self.assertEqual(tuple(mask.shape), (1, 96, 128))
        self.assertTrue(torch.equal(image[..., 0], mask))

    def test_same_seed_is_repeatable(self):
        kwargs = {
            "width": 96,
            "height": 64,
            "top_y_percent": 25.0,
            "bottom_y_percent": 75.0,
            "top_thickness": 6,
            "bottom_thickness": 9,
            "roughness": 10,
            "seed": 456,
        }
        first_image, first_mask = self.module.TornEdgeLines().generate(**kwargs)
        second_image, second_mask = self.module.TornEdgeLines().generate(**kwargs)
        self.assertTrue(torch.equal(first_image, second_image))
        self.assertTrue(torch.equal(first_mask, second_mask))


if __name__ == "__main__":
    unittest.main()
