"""Monument metadata and local relationships from full prefab hierarchies."""

import math

from hierarchy import nodes

TYPES = ("cave", "airport", "building", "town", "radtown", "lighthouse", "waterWell", "roadside", "mountain", "lake", "oasis", "canyon")
FACILITIES = {"Recycler", "Workbench", "RepairBench", "ResearchTable", "NPCVendingMachine", "ComputerStation", "MixingTable", "DieselEngine", "CardTable", "WaterWell", "NPCMissionProvider", "NPCSimpleMissionProvider", "VehicleVendor", "BoatBuildingStation"}
PUZZLES = {"PuzzleReset", "CardReader", "FuseBox", "ElectricSwitch", "PressButton", "DoorManipulator", "CustomDoorManipulator", "TimerSwitch"}


def respawn(lo, hi):
    return {"min": lo, "max": hi} if 0 <= lo <= hi and math.isfinite(hi) else None


def candidates(g, entries):
    positive = [e for e in entries if e["weight"] > 0]
    total = sum(e["weight"] for e in positive)
    out = []
    for entry in positive:
        prefab = g.guid_path.get(entry["prefab"].get("guid"))
        out.append({"prefab": prefab, **({"unresolvedGuid": entry["prefab"].get("guid", "")} if not prefab else {}),
                    "weight": entry["weight"], "chance": entry["weight"] / total, "mobile": bool(entry.get("mobile"))})
    return out


def root_for(g, file, component):
    loc = g.resolve(file, component["m_GameObject"])
    seen = set()
    while loc not in seen:
        seen.add(loc)
        go = g._read(*loc)
        transform = next((g.get(loc[0], r["component"]) for r in go["m_Component"]
                          if (t := g.get(loc[0], r["component"])) and "m_Father" in t[2]), None)
        if not transform:
            break
        parent = g.resolve(transform[0], transform[2]["m_Father"])
        if not parent:
            break
        parent_transform = g._read(*parent)
        loc = g.resolve(parent[0], parent_transform["m_GameObject"])
    else:
        raise ValueError("cyclic monument transform parent")
    return loc


def extract(g):
    roots = {}
    for file, _, info in g.of("MonumentInfo"):
        root = root_for(g, file, info)
        roots.setdefault(root, []).append((file, info))
    monuments, reverse, prefab_by_id, unresolved = {}, {}, {}, []
    for prefab, components in g.prefabs.items():
        for _, _, t in components:
            if t.get("prefabID"):
                prefab_by_id[t["prefabID"]] = prefab
    for root, infos in sorted(roots.items()):
        hierarchy = list(nodes(g, *root))
        prefab = hierarchy[0]["name"]
        if not prefab.startswith("assets/"):
            raise ValueError(f"monument root has no prefab path: {prefab}")
        info = infos[0][1]
        record = {
            "name": info["displayPhrase"]["legacyEnglish"] or prefab.rsplit("/", 1)[-1].removesuffix(".prefab"),
            "type": TYPES[info["Type"]] if 0 <= info["Type"] < len(TYPES) else str(info["Type"]),
            "tierMask": info["Tier"], "bounds": info["Bounds"], "safeZone": bool(info["IsSafeZone"]),
            "minWorldSize": info["MinWorldSize"], "allowPatrolHeliCrash": bool(info["AllowPatrolHeliCrash"]),
            "hasDungeonLink": bool(info["HasDungeonLink"]), "areas": [], "spawns": [], "facilities": [],
            "cameras": [], "radiation": [], "puzzles": [], "placedEntities": [],
        }
        component_ids = {(file, t["__pid"]): str(t["__pid"]) for node in hierarchy for _, file, t in node["components"]}

        def location(node, t):
            return {"id": str(t["__pid"]), "path": "/".join(node["path"][1:]), "position": node["position"],
                    "rotation": node["rotation"], "matrix": [value for i, row in enumerate(node["basis"]) for value in [*row, node["position"][i]]],
                    "active": node["active"] and bool(t.get("m_Enabled", True))}

        def references(file, refs):
            result = []
            for ref in refs:
                loc = g.resolve(file, ref)
                if loc in component_ids:
                    result.append(component_ids[loc])
            return result

        for node in hierarchy:
            for cls, file, t in node["components"]:
                here = location(node, t)
                if cls == "MonumentInfo":
                    record["areas"].append({**here, "name": t["displayPhrase"]["legacyEnglish"], "bounds": t["Bounds"], "safeZone": bool(t["IsSafeZone"])})
                if "prefabs" in t and "maxPopulation" in t:
                    points = [{"position": n["position"], "class": c, "active": n["active"]}
                              for n in hierarchy if (node["file"], node["id"]) in n["ancestors"] or (n["file"], n["id"]) == (node["file"], node["id"])
                              for c, _, _ in n["components"] if c.endswith("SpawnPoint")]
                    record["spawns"].append({**here, "class": cls, "candidates": candidates(g, t["prefabs"]), "populationLimit": t["maxPopulation"],
                        "perTick": {"min": t["numToSpawnPerTickMin"], "max": t["numToSpawnPerTickMax"]},
                        "respawn": respawn(t["respawnDelayMin"], t["respawnDelayMax"]), "points": points,
                        "initialSpawn": bool(t["wantsInitialSpawn"]), "preventDuplicates": bool(t["preventDuplicates"]),
                        "enabled": bool(t["isSpawnerActive"]), "resetBehavior": t["resetBehavior"]})
                if cls == "IndividualSpawner":
                    target = g.guid_path.get(t["entityPrefab"].get("guid"))
                    candidate = {"prefab": target, "weight": 1, "chance": 1, "mobile": False,
                                 **({"unresolvedGuid": t["entityPrefab"].get("guid", "")} if not target else {})}
                    record["spawns"].append({**here, "class": cls, "candidates": [candidate],
                        "populationLimit": 1, "respawn": respawn(t["respawnDelayMin"], t["respawnDelayMax"]), "points": [{"position": node["position"], "class": cls, "active": node["active"]}]})
                if cls in FACILITIES:
                    facility = {**here, "class": cls}
                    if cls == "NPCVendingMachine":
                        order = g.get(file, t.get("vendingOrders", {}))
                        if order:
                            facility["shop"] = order[2]["m_Name"]
                    record["facilities"].append(facility)
                if cls == "CCTV_RC":
                    record["cameras"].append({**here, "code": t["rcIdentifier"], "hasPTZ": bool(t["hasPTZ"])})
                if cls == "TriggerRadiation":
                    record["radiation"].append({**here, "tier": t["radiationTier"], "amountOverride": t["RadiationAmountOverride"],
                        "bypassArmor": bool(t["BypassArmor"]), "falloff": t["falloff"], "colliders": node["colliders"]})
                if cls in PUZZLES:
                    puzzle = {**here, "class": cls}
                    for field in ("accessLevel", "accessDuration", "timeBetweenResets", "playersBlockReset", "scaleWithServerPopulation", "pauseUntilLooted"):
                        if field in t:
                            puzzle[field] = t[field]
                    if cls == "PuzzleReset":
                        puzzle["spawnGroups"] = references(file, t["respawnGroups"])
                        puzzle["resetEntities"] = references(file, t["resetEnts"])
                    if "outputs" in t:
                        puzzle["outputs"] = [{"name": s["niceName"], "target": component_ids.get(g.resolve(file, s["connectedTo"]["ioEnt"])), "slot": s["connectedToSlot"]}
                                             for s in t["outputs"] if g.resolve(file, s["connectedTo"]["ioEnt"]) in component_ids]
                    record["puzzles"].append(puzzle)
                # Serialized instances retain their prefabID even when the GameObject is renamed.
                if t.get("prefabID"):
                    target = prefab_by_id.get(t["prefabID"])
                    if target and target != prefab:
                        record["placedEntities"].append({**here, "prefab": target, "class": cls})
        for spawn in record["spawns"]:
            for candidate in spawn["candidates"]:
                if not candidate["prefab"]:
                    unresolved.append({"monument": prefab, "spawn": spawn["id"], "guid": candidate["unresolvedGuid"], "active": spawn["active"]})
                    continue
                reverse.setdefault(candidate["prefab"], []).append({"monument": prefab, "spawn": spawn["id"], "chance": candidate["chance"]})
        for placed in record["placedEntities"]:
            reverse.setdefault(placed["prefab"], []).append({"monument": prefab, "instance": placed["id"]})
        monuments[prefab] = record
    return {"monuments": dict(sorted(monuments.items())), "entities": dict(sorted(reverse.items())), "unresolvedSpawns": unresolved}
