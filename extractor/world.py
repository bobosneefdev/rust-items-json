"""recyclers.json, techtree.json, loot.json, vending.json: data that isn't per item."""

import math

from game import Game

RECYCLER_TYPES = {0: "green", 1: "yellow", 2: "red"}

ERAS = {0: "none", 1: "any", 10: "primitive", 20: "medieval", 30: "frontier", 1000: "modern"}

LOOT_SPAWN_TYPES = {0: "generic", 1: "player", 2: "town", 3: "airdrop", 4: "crashsite", 5: "roadside"}


def recyclers(g: Game) -> list[dict]:
    """Recycler tiers. Item yields in items.json are at efficiency 1.0; multiply by `efficiency`."""
    out = []
    for _f, _p, t in g.of("RecyclerConfig"):
        for c in t["recyclerTypeConfigs"]:
            out.append(
                {
                    "type": RECYCLER_TYPES.get(c["recyclerType"], c["recyclerType"]),
                    "efficiency": round(c["efficiency"], 4),
                    "seconds": round(c["duration"], 4),
                    "powergrid": {
                        "requiredStage": c["requiredPowergridStageToUse"],
                        "efficiencyStage": c["efficiencyBuffPowergridStage"],
                        "efficiency": round(c["powergridEfficiency"], 4),
                        "durationStage": c["durationBuffPowergridStage"],
                        "seconds": round(c["powergridDuration"], 4),
                    },
                }
            )
    return out


def techtree(g: Game, rarity: dict[str, str | None]) -> list[dict]:
    """Workbench tech trees. Node cost follows Workbench.ScrapForResearch (vanilla, no tax)."""
    out = []
    for f, _p, t in g.of("TechTreeData"):
        if t.get("RequireGameMode"):
            continue
        nodes = []
        # Only outputs are serialized; TechTreeData.SetupInputs rebuilds inputs from them at runtime.
        inputs: dict[int, list[int]] = {}
        for n in t["nodes"]:
            for o in n["outputs"]:
                inputs.setdefault(o, []).append(n["id"])
        for n in t["nodes"]:
            item = g.item(f, n["itemDef"])
            node = {"id": n["id"], "inputs": sorted(inputs.get(n["id"], [])), "outputs": n["outputs"]}
            if item:
                node["item"] = item
                cost = n["costOverride"] if n["costOverride"] >= 0 else {"Common": 15, "Uncommon": 30, "Rare": 60}.get(rarity.get(item) or "", 120)
                node["scrap"] = cost
            elif n.get("groupName"):
                node["group"] = n["groupName"]
            nodes.append(node)
        eras = [ERAS.get(e, e) for e in t["AllowedEras"]]
        out.append(
            {
                "name": t["m_Name"],
                "workbench": t["techTreeLevel"] + 1,
                # Workbench.GetTechTrees: a tree shows when its eras are empty or include the server's.
                "vanilla": not eras or "none" in eras,
                "eras": eras,
                "nodes": nodes,
            }
        )
    out.sort(key=lambda x: (x["workbench"], x["name"]))
    return out


def loot(g: Game, npc_sources=()) -> dict:
    """Loot tables and the containers that use them, mirroring LootSpawn / LootContainer.

    A table either lists `items` (each spawned with an amount in [min, max]) or `pick`s one
    weighted sub-table (`extra` repeats it). Containers roll their slots or their table.
    """
    tables = {}
    ids = {}

    def table_id(f, pid):
        key = (f, pid)
        if key not in ids:
            ids[key] = None  # reserve, guards cycles
            got = g._read(f, pid)
            if got is None:
                return None
            name = got.get("m_Name") or f"table{pid}"
            # Names repeat across files; suffix until unique.
            base, k = name, 2
            while name in tables:
                name, k = f"{base}#{k}", k + 1
            ids[key] = name
            tables[name] = {}
            body = {}
            items = []
            for it in got.get("items") or []:
                sn = g.item(f, it["itemDef"])
                if not sn:
                    continue
                lo = it["amount"]
                hi = it["maxAmount"] if it["maxAmount"] > lo else lo
                items.append({"item": sn, "min": lo, "max": hi})
            if items:
                body["items"] = items
            picks = []
            for e in got.get("subSpawn") or []:
                # LootSpawn.EnsureFilterUpdated drops sub-tables restricted to other eras.
                if e.get("restrictedEras") and 0 not in e["restrictedEras"]:
                    continue
                loc = g.resolve(f, e["category"])
                child = table_id(*loc) if loc else None
                if child:
                    entry = {"table": child, "weight": e["weight"]}
                    if e["extraSpawns"]:
                        entry["extra"] = e["extraSpawns"]
                    picks.append(entry)
            if picks:
                body["pick"] = picks
            tables[name] = body
        return ids[key]

    containers = {}
    sources = list(g.prefabs.items()) + [(name, [(cls, f, {**t, "lootDefinition": {"m_FileID": 0, "m_PathID": 0}, "maxDefinitionsToSpawn": 0})]) for name, cls, f, t in npc_sources]
    for name, comps in sources:
        for cls, f, t in comps:
            if "lootDefinition" not in t or "LootSpawnSlots" not in t:
                continue
            spawn_type = t.get("SpawnType", 0)
            c = {"type": LOOT_SPAWN_TYPES.get(spawn_type, spawn_type)}
            if "minSecondsBetweenRefresh" in t:
                lo, hi = t["minSecondsBetweenRefresh"], t["maxSecondsBetweenRefresh"]
                c["refresh"] = {"min": lo, "max": hi} if 0 < lo <= hi and math.isfinite(hi) else None
            for field in ("initialLootSpawn", "destroyOnEmpty"):
                if field in t:
                    c[field] = bool(t[field])
            slots = []
            for s in t["LootSpawnSlots"]:
                # LootContainer.FillLoot: slots restricted to other eras don't roll on vanilla servers.
                if s.get("eras") and 0 not in s["eras"]:
                    continue
                loc = g.resolve(f, s["definition"])
                tid = table_id(*loc) if loc else None
                if tid:
                    slot = {"table": tid, "rolls": s["numberToSpawn"], "chance": s["probability"]}
                    if s.get("onlyWithLoadoutNamed"):
                        slot["loadout"] = s["onlyWithLoadoutNamed"]
                    slots.append(slot)
            if slots:
                c["slots"] = slots
            else:
                loc = g.resolve(f, t["lootDefinition"])
                tid = table_id(*loc) if loc else None
                if not tid:
                    continue
                c["table"] = tid
                c["rolls"] = t["maxDefinitionsToSpawn"]
            if t.get("scrapAmount"):
                c["scrap"] = t["scrapAmount"]
            c["class"] = cls
            containers[name] = c
            break
    return {"containers": dict(sorted(containers.items())), "tables": dict(sorted(tables.items()))}


def vending(g: Game) -> list[dict]:
    """NPC shop inventories (outpost, bandit camp, fishing villages...)."""
    out = []
    for f, _p, t in g.of("NPCVendingOrder"):
        orders = []
        for o in t["orders"]:
            sell, cur = g.item(f, o["sellItem"]), g.item(f, o["currencyItem"])
            if not sell or not cur:
                continue
            order = {
                "sell": sell,
                "amount": o["sellItemAmount"],
                "currency": cur,
                "price": o["currencyAmount"],
            }
            if o["sellItemAsBP"]:
                order["blueprint"] = True
            if o["maxStock"] >= 0:
                order["stock"] = o["maxStock"]
            r = o.get("randomDetails") or {}
            if r.get("useRandom"):
                order["randomPrice"] = {"min": r["minPrice"], "max": r["maxPrice"]}
            orders.append(order)
        out.append({"name": t["m_Name"], "orders": orders})
    out.sort(key=lambda x: x["name"])
    return out
