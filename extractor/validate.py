"""Reject broken data before publishing: uv run extractor/validate.py <data_dir>."""

import json
import math
import sys
from pathlib import Path


def validate(root: Path):
    data = {p.name: json.loads(p.read_text()) for p in root.glob("*.json")}
    items = data["items.json"]
    names = {i["shortname"] for i in items}
    if not items or len(names) != len(items) or len({i["id"] for i in items}) != len(items):
        raise ValueError("items must be nonempty with unique shortnames and IDs")
    tables = data["loot.json"]["tables"]

    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"item", "sell", "currency"} and not isinstance(child, (dict, list)) and (not isinstance(child, str) or child not in names):
                    raise ValueError(f"{path}.{key}: unknown item {child!r}")
                if key == "table" and not isinstance(child, (dict, list)) and child not in tables:
                    raise ValueError(f"{path}.table: unknown loot table {child!r}")
                if key in {"chance", "probability"} and (not isinstance(child, (int, float)) or not 0 <= child <= 1):
                    raise ValueError(f"{path}.{key}: probability outside [0, 1]")
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{path}: non-finite number")

    for name, value in data.items():
        walk(value, name)
    for i in items:
        if i.get("icon") and not (root / i["icon"]).is_file():
            raise ValueError(f"missing icon: {i['icon']}")
    print(f"Validated {len(data)} datasets and {len(items)} items")


if __name__ == "__main__":
    validate(Path(sys.argv[1]))
