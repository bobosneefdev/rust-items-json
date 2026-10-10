"""World entities, harvesting, NPC attacks/loadouts and NPC loot sources."""

from hierarchy import prefab_nodes
from loot_stats import calculate
from raid import DAMAGE_TYPES, _protection
import world

ANIMALS = {"Bear", "PolarBear", "Boar", "Stag", "Wolf", "Wolf2", "Chicken", "Cow", "Sheep", "Rabbit", "Tiger", "Panther", "Crocodile", "SeaTurtle", "Crabs", "Jellyfish", "Squirrel", "Frog", "SimpleShark", "BaseFishNPC", "RidableHorse", "FarmableAnimal"}
NPCS = {"ScientistNPC", "ScientistNPC2", "NPCPlayer", "TunnelDweller", "UnderwaterDweller", "BanditGuard", "ScarecrowNPC", "GingerbreadNPC", "Zombie", "FrankensteinPet", "NPCShopKeeper", "NPCMissionProvider", "NPCSimpleMissionProvider", "NPCApartmentSecurity"}
VEHICLES = {"Minicopter", "ScrapTransportHelicopter", "AttackHelicopter", "BaseHelicopter", "CH47Helicopter", "CH47HelicopterAIController", "HotAirBalloon", "MotorRowboat", "RHIB", "Tugboat", "Kayak", "PTBoat", "BaseSubmarine", "SubmarineDuo", "BaseVehicle", "BasicCar", "ModularCar", "Bike", "Snowmobile", "TrainEngine", "TrainCar", "BradleyAPC", "CargoShip", "PlayerBoat", "BatteringRam", "Catapult", "Ballista", "SiegeTower", "MLRS", "MagnetCrane", "Drone"}


def nested(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested(child)


def amounts(g, file, values):
    out = []
    for value in values:
        item = g.item(file, value["itemDef"])
        if not item:
            raise ValueError("unresolved world item reference")
        out.append({"item": item, "amount": value["amount"]})
    return out


def loadout(g, file, ref, visiting=None):
    got = g.get(file, ref)
    if not got:
        raise ValueError("unresolved NPC loadout")
    file, pid, t = got
    key = file, pid
    visiting = set() if visiting is None else visiting
    if key in visiting:
        raise ValueError("cyclic NPC loadout")
    base = loadout(g, file, t["giveBase"], visiting | {key}) if t.get("giveBase", {}).get("m_PathID") else {"belt": [], "main": [], "wear": []}
    inventories = {}
    for slot in ("belt", "main", "wear"):
        entries = amounts(g, file, t.get(slot) or [])
        inventories[slot] = ([] if entries and t.get("Strip" + slot.title()) else base[slot]) + entries
    return {"name": t["m_Name"], **inventories, "items": [item for entries in inventories.values() for item in entries]}


def extract(g):
    entities, npc_sources = {}, []
    for prefab, root in sorted(g.prefabs.items()):
        classes = {cls for cls, _, _ in root}
        kind = ("animal" if classes & ANIMALS else "npc" if classes & NPCS else "vehicle" if classes & VEHICLES
                else "collectable" if "CollectibleEntity" in classes else "resource" if classes & {"ResourceEntity", "OreResourceEntity", "TreeEntity", "ResourceDispenser"} else None)
        if kind is None:
            continue
        rec = {"type": kind, "classes": sorted(c for c in classes if c), "name": prefab.rsplit("/", 1)[-1].removesuffix(".prefab")}
        health = next(((f, t) for _, f, t in root if t.get("startHealth", 0) > 0), None)
        if health:
            file, t = health
            rec["health"] = t["startHealth"]
            rec["protection"] = _protection(g, file, t.get("baseProtection", {}))
        harvest, attacks, loadouts, loot_slots = [], [], [], []
        nodes = list(prefab_nodes(g, prefab))
        for node in nodes:
            for cls, file, t in node["components"]:
                if cls == "PrefabInformation" and t.get("title", {}).get("legacyEnglish"):
                    rec["name"] = t["title"]["legacyEnglish"]
                if cls in {"ResourceDispenser", "HumanBodyResourceDispenser"}:
                    harvest.append({"type": {0: "tree", 1: "ore", 2: "flesh"}.get(t["gatherType"], "other"),
                                    "items": amounts(g, file, t["containedItems"]), "finishBonus": amounts(g, file, t["finishBonus"])})
                if cls == "CollectibleEntity":
                    rec["name"] = t["itemName"]["legacyEnglish"] or rec["name"]
                    rec["pickup"] = amounts(g, file, t["itemList"])
                if "fuelPerSec" in t:
                    rec["fuelPerSecond"] = t["fuelPerSec"]
                if "numSlots" in t and cls not in {"NPCPlayer", "ScientistNPC"}:
                    rec.setdefault("storage", []).append({"class": cls, "slots": t["numSlots"]})
                for field in ("fuelStoragePrefab", "storagePrefab"):
                    reference = t.get(field, {})
                    child = g.guid_path.get(reference.get("guid"))
                    if child:
                        rec.setdefault("storage", []).extend({"class": child_class, "prefab": child, "slots": child_t["numSlots"]}
                            for child_class, _, child_t in g.prefabs.get(child, []) if "numSlots" in child_t)
                for ref in t.get("loadouts", []):
                    loadouts.append(loadout(g, file, ref))
                for state in nested(t):
                    if state.get("LootSpawnSlots"):
                        loot_slots.append((cls, file, state))
                    if "CorpsePrefab" in state:
                        corpse = g.guid_path.get(state["CorpsePrefab"].get("guid"))
                        if corpse:
                            rec["corpse"] = corpse
                    if "Damage" in state and "DamageType" in state and isinstance(state["Damage"], (int, float)):
                        damage_type = state["DamageType"]
                        attacks.append({"class": cls, "damage": {DAMAGE_TYPES[damage_type]: state["Damage"]}})
        if rec.get("corpse"):
            for node in prefab_nodes(g, rec["corpse"]):
                for cls, file, t in node["components"]:
                    if cls in {"ResourceDispenser", "HumanBodyResourceDispenser"}:
                        harvest.append({"type": "flesh", "items": amounts(g, file, t["containedItems"]), "finishBonus": amounts(g, file, t["finishBonus"])})
        if harvest:
            rec["harvest"] = harvest
        if attacks:
            rec["attacks"] = attacks
        if loadouts:
            rec["loadouts"] = loadouts
        # Each NPC's death state lives either on its main component or inside an FSM component.
        if loot_slots:
            if len({file for _, file, _ in loot_slots}) != 1:
                raise ValueError(f"NPC loot spans multiple files: {prefab}")
            cls, file, _ = loot_slots[0]
            npc_sources.append((prefab, cls, file, {"SpawnType": 1, "LootSpawnSlots": [slot for _, _, state in loot_slots for slot in state["LootSpawnSlots"]]}))
            rec["loot"] = prefab
        entities[prefab] = rec
    loot = world.loot(g, npc_sources)
    loot["containers"] = {prefab: loot["containers"][prefab] for prefab, _, _, _ in npc_sources if prefab in loot["containers"]}
    # Preserve loadout-conditional drops as separate variants rather than inventing a mixture.
    variants, variant_keys = {}, {}
    for prefab, container in loot["containers"].items():
        names = {slot["loadout"] for slot in container.get("slots", []) if slot.get("loadout")}
        for name in sorted(names | {""}):
            key = prefab + "#" + name
            variants[key] = {**container, "slots": [slot for slot in container["slots"] if not slot.get("loadout") or slot["loadout"] == name]}
            if not variants[key]["slots"]:
                del variants[key]
                continue
            variant_keys[key] = prefab, name
    probabilities = calculate({"tables": loot["tables"], "containers": variants})
    drops, sources = {}, {}
    for key, rows in probabilities["containers"].items():
        prefab, name = variant_keys[key]
        drops.setdefault(prefab, {})[name or "default"] = rows
        for row in rows:
            sources.setdefault(row["item"], []).append({"entity": prefab, **({"loadout": name} if name else {}), **{k: v for k, v in row.items() if k != "item"}})
    return {"entities": entities, "loot": loot, "drops": drops, "sources": dict(sorted(sources.items()))}
