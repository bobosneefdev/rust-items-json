import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from monuments import candidates, respawn
from hierarchy import nodes


class MonumentTest(unittest.TestCase):
    def test_affine_hierarchy_preserves_nonuniform_scale_after_rotation(self):
        class Game:
            def __init__(self):
                self.values = {}
                self.files = {"scene": SimpleNamespace(objects={})}
                for pid in range(1, 5):
                    self.values[pid] = {"m_Name": "same", "m_Component": [{"component": {"m_PathID": pid + 10}}]}
                    self.values[pid + 10] = {
                        "m_Children": [{"m_PathID": pid + 11}] if pid < 4 else [],
                        "m_GameObject": {"m_PathID": pid},
                        "m_LocalPosition": dict(zip("xyz", [1, 0, 0] if pid >= 3 else [0, 0, 0])),
                        "m_LocalRotation": dict(zip("xyzw", [0, 0, math.sqrt(0.5), math.sqrt(0.5)] if pid == 3 else [0, 0, 0, 1])),
                        "m_LocalScale": dict(zip("xyz", [2, 1, 1] if pid == 2 else [1, 1, 1])),
                    }
                    self.files["scene"].objects[pid + 10] = SimpleNamespace(type=SimpleNamespace(name="Transform"))

            def resolve(self, file, ref):
                return file, ref["m_PathID"]

            def _read(self, file, pid):
                return self.values[pid]

            def class_of(self, file, tree):
                return None

        leaf = list(nodes(Game(), "scene", 1))[-1]
        for actual, expected in zip(leaf["position"], [2, 1, 0]):
            self.assertAlmostEqual(actual, expected)
        for actual, expected in zip(sum(leaf["basis"], []), [0, -2, 0, 1, 0, 0, 0, 0, 1]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(leaf["ancestors"], [("scene", 1), ("scene", 2), ("scene", 3)])

    def test_weighted_spawn_choices(self):
        class Game:
            guid_path = {"a": "crate", "b": "barrel"}
        result = candidates(Game(), [{"prefab": {"guid": "a"}, "weight": 3}, {"prefab": {"guid": "b"}, "weight": 2}])
        self.assertEqual([r["chance"] for r in result], [0.6, 0.4])

    def test_disabled_respawn_is_json_null(self):
        self.assertIsNone(respawn(math.inf, math.inf))
        self.assertEqual(respawn(1800, 2200), {"min": 1800, "max": 2200})

    def test_unresolved_candidates_retain_their_probability_and_guid(self):
        class Game:
            guid_path = {}
        result = candidates(Game(), [{"prefab": {"guid": "missing"}, "weight": 1}])
        self.assertEqual(result[0]["unresolvedGuid"], "missing")
        self.assertIsNone(result[0]["prefab"])
        self.assertEqual(result[0]["chance"], 1)


if __name__ == "__main__":
    unittest.main()
