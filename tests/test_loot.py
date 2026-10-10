import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from loot_stats import calculate


class LootTest(unittest.TestCase):
    def test_weighted_repeated_rolls_and_reverse_index(self):
        loot = {"tables": {
            "wood": {"items": [{"item": "wood", "min": 1, "max": 3}]},
            "empty": {},
            "root": {"pick": [{"table": "wood", "weight": 1, "extra": 1}, {"table": "empty", "weight": 1}]},
        }, "containers": {"crate": {"type": "town", "slots": [{"table": "root", "rolls": 2, "chance": 0.5}], "scrap": 2}}}
        result = calculate(loot, {"wood": {"min": 0.1, "max": 0.2}})
        wood = next(x for x in result["containers"]["crate"] if x["item"] == "wood")
        self.assertEqual(wood["chance"], 1 - 0.75 ** 2)
        self.assertEqual(wood["expectedAmount"], 1.5)
        self.assertEqual((wood["min"], wood["max"]), (0, 8))
        self.assertEqual(wood["condition"], {"min": 0.1, "max": 0.2})
        self.assertEqual(result["items"]["wood"][0]["container"], "crate")

    def test_duplicate_items_and_zero_quantity(self):
        result = calculate({"tables": {"root": {"items": [
            {"item": "wood", "min": 2, "max": 2}, {"item": "wood", "min": 3, "max": 3},
            {"item": "stone", "min": 0, "max": 1},
        ]}}, "containers": {"crate": {"table": "root", "rolls": 1}}})
        self.assertEqual(result["containers"]["crate"], [{"item": "wood", "chance": 1.0, "expectedAmount": 5, "min": 5, "max": 5}])

    def test_cycles_and_missing_tables_are_errors(self):
        for tables in ({"a": {"pick": [{"table": "a", "weight": 1}]}}, {}):
            with self.assertRaises(ValueError):
                calculate({"tables": tables, "containers": {"crate": {"table": "a"}}})


if __name__ == "__main__":
    unittest.main()
