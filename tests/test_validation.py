import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extractor"))
from changelog import changelog
from validate import validate


class PublishingTest(unittest.TestCase):
    def test_unknown_item_rejects_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "items.json").write_text(json.dumps([{"id": 1, "shortname": "wood"}]))
            (root / "loot.json").write_text(json.dumps({"tables": {}, "containers": {}}))
            (root / "new-dataset.json").write_text(json.dumps({"item": "missing"}))
            with self.assertRaisesRegex(ValueError, "unknown item"):
                validate(root)

    def test_new_datasets_get_release_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old", Path(tmp) / "new"
            old.mkdir()
            new.mkdir()
            (new / "world.json").write_text("[]")
            self.assertIn("world.json", changelog(old, new, "123"))


if __name__ == "__main__":
    unittest.main()
