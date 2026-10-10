import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from hierarchy import multiply, rotate
from raid import _apply, raid


class CombatTest(unittest.TestCase):
    def test_directional_protection_and_exact_damage(self):
        blocks = [{"prefab": "wall", "softSide": {"name": "hard", "amounts": {"slash": 0.9}}, "grades": [
            {"grade": "stone", "health": 500, "protection": {"name": "base", "amounts": {"slash": 0.5}}}]}]
        result = raid(blocks, [], [{"item": "tool", "damage": {"slash": 20}}])[0]
        self.assertEqual(result["explosives"]["tool"]["soft"], 50)
        self.assertAlmostEqual(result["explosives"]["tool"]["hardDamage"], 1)
        self.assertEqual(result["explosives"]["tool"]["hard"], 500)
        self.assertAlmostEqual(_apply({"explosion": 550}, {"amounts": {"explosion": 0.5}}), 275)

    def test_hierarchy_rotation(self):
        q = [0, math.sqrt(0.5), 0, math.sqrt(0.5)]
        self.assertAlmostEqual(rotate(q, [1, 0, 0])[2], -1)
        self.assertAlmostEqual(multiply(q, q)[1], 1)


if __name__ == "__main__":
    unittest.main()
