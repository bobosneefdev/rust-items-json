import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from item_properties import repair_ingredients


class RepairTest(unittest.TestCase):
    def test_component_replacement_merges_material_costs(self):
        self.assertEqual(repair_ingredients([
            {"item": "metal.refined", "amount": 50}, {"item": "riflebody", "amount": 1},
            {"item": "metalspring", "amount": 4}, {"item": "wood", "amount": 200},
        ], {"riflebody": None, "metalspring": {"item": "metal.refined", "amount": 2}}), [
            {"item": "metal.refined", "amount": 58}, {"item": "wood", "amount": 200}])

    def test_cycles_fail(self):
        with self.assertRaises(ValueError):
            repair_ingredients([{"item": "a", "amount": 1}], {"a": {"item": "b", "amount": 1}, "b": {"item": "a", "amount": 1}})


if __name__ == "__main__":
    unittest.main()
