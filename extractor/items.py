"""items.json and icons/: every item with its IO wiring, crafting, research and recycling."""

from pathlib import Path

from PIL import Image
from UnityPy.export.Texture2DConverter import parse_image_data

from game import Game, english

IO_TYPES = {0: "electric", 1: "fluid", 2: "kinetic", 3: "generic", 4: "industrial"}

ICON_SIZE = 256

# Some entities spawn their wiring on a child prefab (furnaces, computer station, frames, weapon
# racks, vehicle fuel tanks). Those are referenced by guid from fields like these.
SUB_IO_FIELDS = ("IoEntity", "ioSubEntityPrefab", "IOSubEntity", "LightPrefab", "storageUnitPrefab")

# Recycler.RecycleThink: each ingredient yields amount / amountToCreate * efficiency, with the
# fractional part rolled as a chance. Scrap from recycling scales with efficiency / 0.5.
# Categories that can't be recycled (Recycler.CanBeRecycled).
NOT_RECYCLABLE = {"Food"}


def _io(t: dict) -> dict:
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


def prefab_io(g: Game) -> dict[str, dict]:
    """Prefab path -> IO slots, following child-IO links."""
    out, sub = {}, {}
    for name, comps in g.prefabs.items():
        for cls, _f, t in comps:
            if isinstance(t.get("inputs"), list) and isinstance(t.get("outputs"), list):
                out[name] = {"class": cls, **_io(t)}
            for guid in _guid_fields(t):
                if guid in g.guid_path:
                    sub.setdefault(name, g.guid_path[guid])
    for parent, child in sub.items():
        if parent not in out and child in out:
            out[parent] = out[child]
    return out


def icons(g: Game, refs: dict[str, dict], out_dir: Path) -> set[str]:
    """Decode each item's icon by reading only its texture's byte range."""
    by_cab = {b.cab: b for b in g.textures}
    sfs = {cab: b.serialized() for cab, b in by_cab.items()}
    ext = [e.path.split("/")[-1] for e in g.items_file.externals]
    out_dir.mkdir(parents=True, exist_ok=True)
    done = set()
    for shortname, ref in refs.items():
        fid = ref["m_FileID"]
        if fid == 0:
            continue  # the few icons stored inside items.preload are UI placeholders
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


def research_scrap(rarity: str | None, default_blueprint: bool) -> int:
    """ResearchTable.ScrapForResearch with vanilla convars."""
    if default_blueprint:
        return 10
    return {"Common": 15, "Uncommon": 30, "Rare": 60}.get(rarity or "", 120)


def extract(g: Game, out: Path) -> list[dict]:
    io = prefab_io(g)
    items = g.items()
    records = []
    icon_refs = {}
    for sn, comps in items.items():
        d = comps["ItemDefinition"]
        j = g.plain.get(d["itemid"], {})
        rec = {
            "id": d["itemid"],
            "shortname": sn,
            "name": english(j.get("Name"), d["displayName"]["legacyEnglish"]),
            "description": english(j.get("Description"), d["displayDescription"]["legacyEnglish"]),
            "category": j.get("Category"),
            "stackable": d["stackable"],
            "rarity": j.get("rarity"),
            "hidden": bool(d["hidden"]),
            "condition": {"enabled": bool(d["condition"]["enabled"]), "max": d["condition"]["max"]},
        }
        # The placed entity: a deployable, else any other mod that spawns one (vehicle modules, pagers...).
        # ItemModEntity on deployables is the building planner, so it comes last.
        mods = sorted(
            (c for c in comps if c and c.startswith("ItemMod") and "entityPrefab" in comps[c]),
            key=lambda c: (c != "ItemModDeployable", c == "ItemModEntity"),
        )
        prefab = next((g.guid_path[x] for c in mods if (x := comps[c]["entityPrefab"].get("guid")) in g.guid_path), None)
        if prefab:
            rec["entity"] = prefab
            if prefab in io:
                rec["io"] = io[prefab]

        bp = comps.get("ItemBlueprint")
        if bp:
            ingredients = [{"item": g.item(g.items_file.name, i["itemDef"]), "amount": i["amount"]} for i in bp["ingredients"]]
            rec["crafting"] = {
                "ingredients": ingredients,
                "amount": bp["amountToCreate"],
                "time": bp["time"],
                "workbench": bp["workbenchLevelRequired"],
                "craftable": bool(bp["userCraftable"]),
                "researchable": bool(bp["isResearchable"]),
                "defaultBlueprint": bool(bp["defaultBlueprint"]),
            }
            if bp["isResearchable"]:
                rec["crafting"]["researchScrap"] = research_scrap(rec["rarity"], bool(bp["defaultBlueprint"]))
            if rec["category"] not in NOT_RECYCLABLE:
                # Per item recycled at efficiency 1.0 (multiply by the recycler's efficiency).
                yields = [
                    {"item": i["item"], "amount": round(i["amount"] / bp["amountToCreate"], 4)}
                    for i in ingredients
                    if i["item"] and i["item"] != "scrap"
                ]
                scrap = bp["scrapFromRecycle"] * 2  # RecycleThink scales scrap by efficiency / 0.5
                if scrap:
                    yields.insert(0, {"item": "scrap", "amount": scrap})
                if yields:
                    rec["recycle"] = yields
        records.append(rec)
        icon_refs[sn] = d["iconSprite"]

    have = icons(g, icon_refs, out / "icons")
    for r in records:
        if r["shortname"] in have:
            r["icon"] = f"icons/{r['shortname']}.webp"
    records.sort(key=lambda r: r["shortname"])
    return records
