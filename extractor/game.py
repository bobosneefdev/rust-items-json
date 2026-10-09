"""Loads Rust's bundles once and resolves references between them.

Unity stores references as (m_FileID, m_PathID): file 0 is the referencing file itself, N is
its Nth external. `Game.resolve` follows those across every loaded file, so extractors can walk
from a loot table to its items or from a building grade to its protection without caring which
bundle each asset lives in.
"""

import json
from collections import defaultdict
from pathlib import Path

from UnityPy.files import SerializedFile
from UnityPy.streams import EndianBinaryReader

from bundle import Bundle


def _files(b: Bundle) -> dict[str, SerializedFile]:
    out = {}
    for name, (off, size) in b.nodes.items():
        if name.endswith((".resS", ".resource")):
            continue
        out[name] = SerializedFile(EndianBinaryReader(memoryview(b._mm)[off : off + size]), name=name)
    return out


def english(localized: str | None, legacy: str) -> str:
    """The plain item JSON has current English text, but untranslated entries come through as "#token"."""
    return localized if localized and not localized.startswith("#") else legacy


# Script classes every extractor might ask for via Game.of().
INDEXED = {
    "GameManifest",
    "ItemDefinition",
    "ItemBlueprint",
    "TechTreeData",
    "LootSpawn",
    "NPCVendingOrder",
    "BuildingGrade",
    "ProtectionProperties",
    "RecyclerConfig",
}


class Game:
    def __init__(self, server: Path, client: Path):
        shared = server / "Bundles" / "shared"
        self.content = Bundle(shared / "content.bundle")
        self.scenes = Bundle(shared / "assetscenes.bundle")
        self.items_bundle = Bundle(client / "items.preload.bundle")
        self.textures = [Bundle(p) for p in sorted(client.glob("textures.*.bundle"))]

        self.files: dict[str, SerializedFile] = {}
        self.files.update(_files(self.content))
        self.files.update(_files(self.scenes))
        self.items_file = self.items_bundle.serialized()
        self.files[self.items_file.name] = self.items_file

        self._scripts = {
            (n, pid): o.read().m_ClassName
            for n, f in self.files.items()
            for pid, o in f.objects.items()
            if o.type.name == "MonoScript"
        }
        self._ext = {n: [e.path.split("/")[-1] for e in f.externals] for n, f in self.files.items()}
        self._cache: dict[tuple[str, int], dict | None] = {}
        self._by_class: dict[str, list[tuple[str, int, dict]]] | None = None

        self.plain = {}
        for p in (server / "Bundles" / "items").glob("*.json"):
            j = json.loads(p.read_text())
            self.plain[j["itemid"]] = j

        self.index(INDEXED)
        self.guid_path = {p["guid"]: p["name"] for _f, _p, t in self.of("GameManifest") for p in t["prefabProperties"]}
        # ItemDefinitions exist in items.preload and again on the .item.prefab copies in the asset
        # scenes; references can point at either, so both resolve to the shortname.
        self.item_by_ref = {(f, pid): t["shortname"] for f, pid, t in self.of("ItemDefinition")}

    # --- typetrees -----------------------------------------------------------------------------

    def _read(self, fname: str, pid: int) -> dict | None:
        key = (fname, pid)
        if key in self._cache:
            return self._cache[key]
        o = self.files[fname].objects.get(pid)
        try:
            return o.read_typetree() if o is not None else None
        except Exception:
            return None

    def resolve(self, fname: str, ref: dict) -> tuple[str, int] | None:
        """(file, pathid) a PPtr in `fname` points to, if that file is loaded."""
        fid, pid = ref.get("m_FileID", 0), ref.get("m_PathID", 0)
        if pid == 0:
            return None
        target = fname if fid == 0 else self._ext[fname][fid - 1]
        return (target, pid) if target in self.files else None

    def get(self, fname: str, ref: dict) -> tuple[str, int, dict] | None:
        loc = self.resolve(fname, ref)
        if not loc:
            return None
        t = self._read(*loc)
        if t is not None:
            self._cache[loc] = t
        return (loc[0], loc[1], t) if t is not None else None

    def item(self, fname: str, ref: dict) -> str | None:
        """Shortname an ItemDefinition PPtr points to."""
        loc = self.resolve(fname, ref)
        return self.item_by_ref.get(loc) if loc else None

    def class_of(self, fname: str, t: dict) -> str | None:
        ref = t.get("m_Script")
        if not ref:
            return None
        loc = self.resolve(fname, ref)
        return self._scripts.get(loc) if loc else None

    def index(self, classes: set[str]):
        """One pass over every MonoBehaviour: keeps the wanted classes anywhere, plus every
        component sitting on a root prefab object (named by its asset path)."""
        self._by_class = defaultdict(list)
        self.prefabs: dict[str, list[tuple[str | None, str, dict]]] = defaultdict(list)
        for n, f in self.files.items():
            in_prefabs = n.startswith("BuildPlayer-AssetScene-") and not n.endswith(".sharedAssets")
            for pid, o in f.objects.items():
                if o.type.name != "MonoBehaviour":
                    continue
                t = self._read(n, pid)
                if t is None:
                    continue
                c = self.class_of(n, t)
                keep = c in classes
                if in_prefabs:
                    go = f.objects.get(t["m_GameObject"]["m_PathID"])
                    name = go.peek_name() if go else ""
                    if name.startswith("assets/") and name.endswith(".prefab"):
                        self.prefabs[name].append((c, n, t))
                        keep = True
                if keep:
                    t["__pid"] = pid
                    self._cache[(n, pid)] = t
                    if c:
                        self._by_class[c].append((n, pid, t))

    def items(self) -> dict[str, dict[str, dict]]:
        """Canonical item assets: shortname -> {class: typetree} for the ItemDefinition and its
        sibling components (blueprint, mods) in items.preload."""
        by_go: dict[int, dict] = defaultdict(dict)
        for pid, o in self.items_file.objects.items():
            if o.type.name != "MonoBehaviour":
                continue
            t = self._read(self.items_file.name, pid)
            if t is None:
                continue
            t["__pid"] = pid
            by_go[t["m_GameObject"]["m_PathID"]][self.class_of(self.items_file.name, t)] = t
        return {c["ItemDefinition"]["shortname"]: c for c in by_go.values() if "ItemDefinition" in c}

    def of(self, cls: str) -> list[tuple[str, int, dict]]:
        """Every MonoBehaviour of an indexed script class, across all loaded files."""
        assert self._by_class is not None, "call index() first"
        return self._by_class.get(cls, [])
