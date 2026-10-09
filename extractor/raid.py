"""building.json and raid.json: building blocks, doors and other raidable entities, explosives,
and how many of each explosive destroys each target.

Damage follows BaseCombatEntity.Hurt: every damage type is scaled by (1 - protection[type]),
first by the target's base protection, then by its direction (soft side) protection when the hit
isn't on the weak side. The hit count is ceil(health / damage per hit). Explosives use their
full damage list, i.e. a hit at the centre of the blast.
"""

import math

from game import Game

DAMAGE_TYPES = [
    "generic", "hunger", "thirst", "cold", "drowned", "heat", "bleeding", "poison", "suicide",
    "bullet", "slash", "blunt", "fall", "radiation", "bite", "stab", "explosion", "radiationExposure",
    "coldExposure", "decay", "electricShock", "arrow", "antiVehicle", "collision", "funWater",
    "beeSting", "paintball", "cannon",
]  # fmt: skip

GRADES = {0: "twig", 1: "wood", 2: "stone", 3: "metal", 4: "armored"}

# Fields that lead from an item's spawned entity to the thing that actually explodes.
EXPLOSIVE_LINKS = ("prefabToThrow", "projectileObject", "entityPrefab", "explosionPrefab")


def _protection(g: Game, f: str, ref: dict) -> dict | None:
    got = g.get(f, ref)
    if not got:
        return None
    _f, _p, t = got
    amounts = {DAMAGE_TYPES[i]: round(v, 4) for i, v in enumerate(t["amounts"]) if v and i < len(DAMAGE_TYPES)}
    return {"name": t["m_Name"], "amounts": amounts}


def _damage(entries: list[dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in entries:
        k = DAMAGE_TYPES[e["type"]] if e["type"] < len(DAMAGE_TYPES) else str(e["type"])
        out[k] = out.get(k, 0) + e["amount"]
    return out


def _apply(damage: dict[str, float], *protections: dict | None) -> float:
    total = 0.0
    for k, v in damage.items():
        for p in protections:
            if p:
                v *= 1 - max(-1.0, min(1.0, p["amounts"].get(k, 0)))
        total += v
    return total


def _direction(g: Game, prefab: str) -> dict | None:
    for cls, f, t in g.prefabs.get(prefab, []):
        if cls == "DirectionProperties" and t.get("extraProtection"):
            return _protection(g, f, t["extraProtection"])
    return None


def building(g: Game) -> list[dict]:
    """Building blocks (walls, foundations...) per grade: health, cost and protection."""
    out = []
    for prefab, comps in g.prefabs.items():
        construction = next((t for c, _f, t in comps if c == "Construction"), None)
        if not construction or not any(c == "BuildingBlock" for c, _f, _t in comps):
            continue
        grades = []
        for cls, f, t in comps:
            if cls != "ConstructionGrade":
                continue
            got = g.get(f, t["gradeBase"])
            if not got:
                continue
            gf, _p, gb = got
            if gb.get("skin"):
                continue  # cosmetic grade skins share the base grade's stats
            grade = GRADES.get(gb["type"], gb["type"])
            cost = [
                {"item": g.item(gf, c["itemDef"]), "amount": math.ceil(c["amount"] * construction["costMultiplier"])}
                for c in gb["baseCost"]
            ]
            grades.append(
                {
                    "grade": grade,
                    "health": gb["baseHealth"] * construction["healthMultiplier"],
                    "cost": cost,
                    "protection": _protection(g, gf, gb["damageProtecton"]),
                }
            )
        if not grades:
            continue
        grades.sort(key=lambda x: list(GRADES.values()).index(x["grade"]) if x["grade"] in GRADES.values() else 99)
        out.append(
            {
                "prefab": prefab,
                "name": construction["info"]["name"]["legacyEnglish"],
                "grades": grades,
                "softSide": _direction(g, prefab),
            }
        )
    out.sort(key=lambda x: x["prefab"])
    return out


def deployables(g: Game, entity_of: dict[str, str]) -> list[dict]:
    """Raidable placed items (doors, hatches, walls, turrets...): health and protection."""
    out = []
    for sn, prefab in entity_of.items():
        for cls, f, t in g.prefabs.get(prefab, []):
            if not t.get("baseProtection") or not t.get("startHealth") or t["startHealth"] <= 0:
                continue
            prot = _protection(g, f, t["baseProtection"])
            if not prot:
                continue
            out.append({"item": sn, "prefab": prefab, "class": cls, "health": t["startHealth"], "protection": prot, "softSide": _direction(g, prefab)})
            break
    out.sort(key=lambda x: x["item"])
    return out


def _explosive(g: Game, prefab: str, depth: int = 0) -> dict | None:
    comps = g.prefabs.get(prefab, [])
    for cls, _f, t in comps:
        if isinstance(t.get("damageTypes"), list) and t["damageTypes"] and "explosionRadius" in t:
            return {
                "prefab": prefab,
                "class": cls,
                "damage": _damage(t["damageTypes"]),
                "radius": round(t["explosionRadius"], 4),
                "minRadius": round(t.get("minExplosionRadius", 0), 4),
            }
    if depth >= 3:
        return None
    for _cls, _f, t in comps:
        for k in EXPLOSIVE_LINKS:
            ref = t.get(k)
            if isinstance(ref, dict) and ref.get("guid") in g.guid_path:
                found = _explosive(g, g.guid_path[ref["guid"]], depth + 1)
                if found:
                    return found
    return None


def explosives(g: Game, items: dict[str, dict]) -> list[dict]:
    """Items that explode: their damage list at the blast centre and blast radius."""
    out = []
    for sn, comps in items.items():
        for t in comps.values():
            hit = None
            for k in EXPLOSIVE_LINKS:
                ref = t.get(k)
                if isinstance(ref, dict) and ref.get("guid") in g.guid_path:
                    hit = _explosive(g, g.guid_path[ref["guid"]])
                    if hit:
                        break
            if hit:
                out.append({"item": sn, **hit})
                break
        else:
            # Ammo with a radial explosion on impact (explosive rounds); bullet damage itself
            # barely scratches building blocks, so the blast is what counts for raiding.
            radial = comps.get("ItemModProjectileRadialDamage")
            if radial and radial["damage"]["amount"] > 0:
                out.append(
                    {
                        "item": sn,
                        "class": "ItemModProjectileRadialDamage",
                        "damage": _damage([radial["damage"]]),
                        "radius": round(radial["radius"], 4),
                        "minRadius": 0,
                    }
                )
    out.sort(key=lambda x: x["item"])
    return out


def raid(blocks: list[dict], deploys: list[dict], booms: list[dict]) -> list[dict]:
    """Explosives needed to destroy each target, hard side and soft side."""
    targets = []
    for b in blocks:
        for gr in b["grades"]:
            targets.append(({"prefab": b["prefab"], "grade": gr["grade"]}, gr["health"], gr["protection"], b["softSide"]))
    for d in deploys:
        targets.append(({"item": d["item"]}, d["health"], d["protection"], d["softSide"]))

    out = []
    for target, health, prot, soft in targets:
        costs = {}
        for e in booms:
            hard = _apply(e["damage"], prot, soft)
            weak = _apply(e["damage"], prot)
            entry = {}
            if hard > 0.01:
                entry["hard"] = math.ceil(health / hard - 1e-9)
            if soft and weak > 0.01 and weak != hard:
                entry["soft"] = math.ceil(health / weak - 1e-9)
            if entry:
                costs[e["item"]] = entry
        if costs:
            out.append({**target, "health": health, "explosives": costs})
    return out
