import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from world_entities import nested, amounts, loadout
from world import loot


class WorldTest(unittest.TestCase):
    def test_npc_loot_does_not_require_container_refresh_fields(self):
        class FakeGame:
            prefabs = {}

            def resolve(self, file, ref):
                return (file, ref["m_PathID"]) if ref.get("m_PathID") else None

            def _read(self, file, pid):
                return {"m_Name": "npc_table", "items": [{"itemDef": {}, "amount": 1, "maxAmount": 1}]}

            def item(self, file, ref):
                return "scrap"

        result = loot(FakeGame(), [("npc", "ScientistNPC2", "file", {"LootSpawnSlots": [
            {"definition": {"m_PathID": 1}, "numberToSpawn": 1, "probability": 1}]} )])
        self.assertEqual(result["containers"]["npc"]["slots"][0]["table"], "npc_table")
        self.assertEqual(result["containers"]["npc"]["type"], "generic")
        self.assertNotIn("refresh", result["containers"]["npc"])

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
