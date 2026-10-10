import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from world_entities import nested, amounts, loadout


class WorldTest(unittest.TestCase):
    def test_nested_death_states_are_discovered(self):
        raw = {"dead": {"CorpsePrefab": {"guid": "corpse"}, "LootSpawnSlots": [{"probability": 0.5}]}}
        slots = [v["LootSpawnSlots"] for v in nested(raw) if "LootSpawnSlots" in v]
        self.assertEqual(slots, [[{"probability": 0.5}]])

    def test_unresolved_harvesting_item_is_an_error(self):
        class FakeGame:
            def item(self, file, ref):
                return None
        with self.assertRaises(ValueError):
            amounts(FakeGame(), "file", [{"itemDef": {}, "amount": 1}])

    def test_inherited_loadouts_honor_inventory_stripping(self):
        class FakeGame:
            def get(self, file, ref):
                if ref["m_PathID"] == 1:
                    return file, 1, {"m_Name": "base", "belt": [{"itemDef": "pistol", "amount": 1}], "wear": [{"itemDef": "shirt", "amount": 1}]}
                return file, 2, {"m_Name": "child", "giveBase": {"m_PathID": 1}, "belt": [{"itemDef": "rifle", "amount": 1}], "StripBelt": True}
            def item(self, file, ref):
                return ref
        result = loadout(FakeGame(), "file", {"m_PathID": 2})
        self.assertEqual(result["belt"], [{"item": "rifle", "amount": 1}])
        self.assertEqual(result["wear"], [{"item": "shirt", "amount": 1}])


if __name__ == "__main__":
    unittest.main()
