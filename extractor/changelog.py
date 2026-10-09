"""Describe what changed between two data/ directories, for release notes and CHANGELOG.md.

Usage: python extractor/changelog.py <old_data_dir> <new_data_dir> <build>
Prints markdown; empty output when nothing changed.
"""

import json
import sys
from pathlib import Path

# Item fields worth calling out; others (descriptions, icons) are summarised as "details".
WATCHED = ("name", "stackable", "rarity", "io", "crafting", "recycle", "category", "hidden")


def _load(d: Path, name: str):
    p = d / name
    return json.loads(p.read_text()) if p.exists() else None


def _items(old: list[dict], new: list[dict]) -> list[str]:
    a = {r["shortname"]: r for r in old}
    b = {r["shortname"]: r for r in new}
    lines = []
    for sn in sorted(b.keys() - a.keys()):
        lines.append(f"- Added **{b[sn]['name']}** (`{sn}`)")
    for sn in sorted(a.keys() - b.keys()):
        lines.append(f"- Removed **{a[sn]['name']}** (`{sn}`)")
    for sn in sorted(a.keys() & b.keys()):
        changed = [k for k in WATCHED if a[sn].get(k) != b[sn].get(k)]
        if not changed and a[sn] != b[sn]:
            changed = ["details"]
        if changed:
            parts = []
            for k in changed:
                if k == "io":
                    io_a, io_b = a[sn].get("io") or {}, b[sn].get("io") or {}
                    na = (len(io_a.get("inputs", [])), len(io_a.get("outputs", [])))
                    nb = (len(io_b.get("inputs", [])), len(io_b.get("outputs", [])))
                    parts.append(f"io {na[0]}in/{na[1]}out → {nb[0]}in/{nb[1]}out" if na != nb else "io")
                elif k in ("name", "stackable", "rarity", "category"):
                    parts.append(f"{k} {a[sn].get(k)!r} → {b[sn].get(k)!r}")
                else:
                    parts.append(k)
            lines.append(f"- `{sn}`: {', '.join(parts)}")
    return lines


def changelog(old: Path, new: Path, build: str) -> str:
    sections = []
    items = _items(_load(old, "items.json") or [], _load(new, "items.json") or [])
    if items:
        sections.append("### Items\n\n" + "\n".join(items))
    others = [
        n
        for n in ("techtree.json", "recyclers.json", "loot.json", "vending.json", "building.json", "explosives.json", "raid.json")
        if _load(old, n) != _load(new, n)
    ]
    if others:
        sections.append("### Other data\n\n" + "\n".join(f"- `{n}` changed" for n in others))
    if not sections:
        return ""
    return f"## Rust build {build}\n\n" + "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    print(changelog(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]), end="")
