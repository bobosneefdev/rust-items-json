"""Extract Rust item data from the game's bundles.

Usage: python extractor/extract.py <server_dir> <client_dir> <out_dir>

server_dir: a RustDedicated download containing Bundles/ (anonymous)
client_dir: Rust client Bundles/shared/{items.preload,textures.*}.bundle (account that owns Rust)
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

from PIL import Image
from UnityPy.export.Texture2DConverter import parse_image_data
from UnityPy.files import SerializedFile
from UnityPy.streams import EndianBinaryReader

from bundle import Bundle

IO_TYPES = {0: "electric", 1: "fluid", 2: "kinetic", 3: "generic", 4: "industrial"}

ICON_SIZE = 256


def scene_files(b: Bundle):
    """Every serialized file in a multi-file bundle (asset scenes), keyed by name."""
    out = {}
    for name, (off, size) in b.nodes.items():
        if name.endswith((".resS", ".resource")):
            continue
        out[name] = SerializedFile(EndianBinaryReader(memoryview(b._mm)[off : off + size]), name=name)
    return out


def behaviours(files: dict[str, SerializedFile], classes: set[str] | None = None):
    """Yield (file, class_name, typetree) for MonoBehaviours, resolving scripts across files."""
    scripts = {
        (n, pid): o.read().m_ClassName for n, f in files.items() for pid, o in f.objects.items() if o.type.name == "MonoScript"
    }
    for n, f in files.items():
        ext = [e.path.split("/")[-1] for e in f.externals]
        for pid, o in f.objects.items():
            if o.type.name != "MonoBehaviour":
                continue
            try:
                t = o.read_typetree()
            except Exception:
                continue
            t["__pid"] = pid
            ref = t["m_Script"]
            fid = ref["m_FileID"]
            cls = scripts.get((n if fid == 0 else ext[fid - 1], ref["m_PathID"]))
            if classes is None or cls in classes:
                yield f, cls, t


def game_manifest(content: Bundle) -> dict[str, str]:
    """Prefab guid -> asset path, from the GameManifest asset."""
    for _f, _c, t in behaviours({content.cab: content.serialized()}, {"GameManifest"}):
        return {p["guid"]: p["name"] for p in t["prefabProperties"]}
    raise RuntimeError("GameManifest not found")


def item_assets(items: SerializedFile):
    """Group item-side components by GameObject: {go_pathid: {class: typetree}}."""
    by_go: dict[int, dict] = defaultdict(dict)
    for _f, cls, t in behaviours({items.name: items}):
        by_go[t["m_GameObject"]["m_PathID"]][cls] = t
    return by_go


def io_slots(t: dict) -> dict:
    def slot(s):
        p = s["handlePosition"]
        return {
            "name": s["niceName"],
            "type": IO_TYPES.get(s["type"], s["type"]),
            "position": [round(p["x"], 4), round(p["y"], 4), round(p["z"], 4)],
        }

    return {
        "ioType": IO_TYPES.get(t.get("ioType"), t.get("ioType")),
        "inputs": [slot(s) for s in t["inputs"]],
        "outputs": [slot(s) for s in t["outputs"]],
    }


# Some entities spawn their wiring on a child prefab (furnaces, computer station, frames, weapon
# racks, vehicle fuel tanks). Those are referenced by guid from fields like these.
SUB_IO_FIELDS = ("IoEntity", "ioSubEntityPrefab", "IOSubEntity", "LightPrefab", "storageUnitPrefab")


def _guid_fields(v):
    if isinstance(v, dict):
        for k, x in v.items():
            if k in SUB_IO_FIELDS and isinstance(x, dict) and x.get("guid"):
                yield x["guid"]
            else:
                yield from _guid_fields(x)
    elif isinstance(v, list):
        for x in v:
            yield from _guid_fields(x)


def prefab_io(scenes: Bundle, guid_path: dict[str, str]) -> dict[str, dict]:
    """Prefab path -> IO slots, from IOEntity components in the prefab asset scene."""
    out = {}
    sub = {}
    for f, cls, t in behaviours(scene_files(scenes)):
        go = f.objects.get(t["m_GameObject"]["m_PathID"])
        name = go.peek_name() if go else ""
        # Root prefab objects are named by their asset path; nested IO children (monument props) aren't.
        if not (name.startswith("assets/") and name.endswith(".prefab")):
            continue
        if isinstance(t.get("inputs"), list) and isinstance(t.get("outputs"), list):
            out[name] = {"class": cls, **io_slots(t)}
        for guid in _guid_fields(t):
            if guid in guid_path:
                sub.setdefault(name, guid_path[guid])
    for parent, child in sub.items():
        if parent not in out and child in out:
            out[parent] = out[child]
    return out


def icons(items: SerializedFile, textures: list[Bundle], refs: dict[str, dict], out_dir: Path) -> set[str]:
    """Decode each item's icon by reading only its texture's byte range."""
    by_cab = {b.cab: b for b in textures}
    sfs = {cab: b.serialized() for cab, b in by_cab.items()}
    ext = [e.path.split("/")[-1] for e in items.externals]
    out_dir.mkdir(parents=True, exist_ok=True)
    done = set()
    for shortname, ref in refs.items():
        fid = ref["m_FileID"]
        if fid == 0:
            continue  # a handful of icons live inside items.preload itself; handled below if needed
        cab = ext[fid - 1]
        sf = sfs.get(cab)
        if sf is None or ref["m_PathID"] not in sf.objects:
            continue
        sprite = sf.objects[ref["m_PathID"]].read_typetree()
        tex_ref = sprite["m_RD"]["texture"]
        if tex_ref["m_FileID"] != 0:
            continue
        tex = sf.objects[tex_ref["m_PathID"]].read_typetree()
        sd = tex["m_StreamData"]
        w, h = tex["m_Width"], tex["m_Height"]
        data = by_cab[cab].read(sd["path"].split("/")[-1], sd["offset"], sd["size"])
        img = parse_image_data(data, w, h, tex["m_TextureFormat"], sf.version, sf.target_platform)
        r = sprite["m_RD"]["textureRect"]
        img = img.crop((int(r["x"]), int(h - r["y"] - r["height"]), int(r["x"] + r["width"]), int(h - r["y"])))
        if img.size != (ICON_SIZE, ICON_SIZE):
            img = img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        img.save(out_dir / f"{shortname}.webp", "WEBP", lossless=True)
        done.add(shortname)
    return done


def main(server: Path, client: Path, out: Path):
    shared = server / "Bundles" / "shared"
    content = Bundle(shared / "content.bundle")
    guid_path = game_manifest(content)
    io = prefab_io(Bundle(shared / "assetscenes.bundle"), guid_path)

    items_bundle = Bundle(client / "items.preload.bundle")
    items = items_bundle.serialized()
    plain = {p.stem: json.loads(p.read_text()) for p in (server / "Bundles" / "items").glob("*.json")}

    assets = item_assets(items)
    by_pid = {}
    records = []
    icon_refs = {}
    for comps in assets.values():
        d = comps.get("ItemDefinition")
        if not d:
            continue
        by_pid[d["__pid"]] = d["shortname"]
    for comps in assets.values():
        d = comps.get("ItemDefinition")
        if not d:
            continue
        sn = d["shortname"]
        j = plain.get(sn, {})
        rec = {
            "id": d["itemid"],
            "shortname": sn,
            "name": d["displayName"]["legacyEnglish"],
            "description": d["displayDescription"]["legacyEnglish"],
            "category": j.get("Category"),
            "stackable": d["stackable"],
            "rarity": j.get("rarity"),
            "hidden": bool(d["hidden"]),
            "condition": {"enabled": bool(d["condition"]["enabled"]), "max": d["condition"]["max"]},
        }
        # The placed entity: a deployable, else any other mod that spawns one (vehicle modules, pagers...).
        # ItemModEntity on deployables is the building planner, so it comes last.
        mods = sorted((c for c in comps if c and c.startswith("ItemMod") and "entityPrefab" in comps[c]), key=lambda c: (c != "ItemModDeployable", c == "ItemModEntity"))
        prefab = next((guid_path[g] for c in mods if (g := comps[c]["entityPrefab"].get("guid")) in guid_path), None)
        if prefab:
            rec["entity"] = prefab
            if prefab in io:
                rec["io"] = io[prefab]
        bp = comps.get("ItemBlueprint")
        if bp:
            rec["crafting"] = {
                "ingredients": [
                    {"item": by_pid.get(i["itemDef"]["m_PathID"]), "amount": i["amount"]} for i in bp["ingredients"]
                ],
                "amount": bp["amountToCreate"],
                "time": bp["time"],
                "workbench": bp["workbenchLevelRequired"],
                "craftable": bool(bp["userCraftable"]),
                "researchable": bool(bp["isResearchable"]),
                "researchScrap": bp["scrapRequired"],
                "defaultBlueprint": bool(bp["defaultBlueprint"]),
            }
            rec["recycle"] = {"scrap": bp["scrapFromRecycle"]}
        records.append(rec)
        icon_refs[sn] = d["iconSprite"]

    textures = [Bundle(p) for p in sorted(client.glob("textures.*.bundle"))]
    have = icons(items, textures, icon_refs, out / "icons")
    for r in records:
        if r["shortname"] in have:
            r["icon"] = f"icons/{r['shortname']}.webp"

    records.sort(key=lambda r: r["shortname"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "items.json").write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(records)} items, {sum('io' in r for r in records)} with IO, {len(have)} icons")


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:4]))
