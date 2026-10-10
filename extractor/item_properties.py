"""Structured gameplay properties from item components and their entity/projectile prefabs."""

from raid import _damage, _protection

METABOLISM = ("calories", "hydration", "heartrate", "poison", "radiation", "bleeding", "health", "healthOverTime")
AREAS = ("head", "chest", "stomach", "arm", "hand", "leg", "foot")


def repair_ingredients(ingredients, components):
    """RepairBench.StripComponentRepairCost: substitute each component's FIRST ingredient."""
    costs = {i["item"]: i["amount"] for i in ingredients}
    steps = 0
    while any(sn in components for sn in costs):
        steps += 1
        if steps > len(components) + len(ingredients):
            raise ValueError("cyclic component repair ingredients")
        sn = next(sn for sn in costs if sn in components)
        amount = costs.pop(sn)
        replacement = components[sn]
        if replacement:
            item = replacement["item"]
            costs[item] = costs.get(item, 0) + max(1, replacement["amount"] * amount)
    return [{"item": sn, "amount": amount} for sn, amount in sorted(costs.items())]


def _fields(raw, fields):
    return {key: raw[source] for key, source in fields.items() if source in raw}


def extract(g, records):
    assets = g.items()
    by_name = {r["shortname"]: r for r in records}
    component_costs = {}
    for sn, cs in assets.items():
        d = cs["ItemDefinition"]
        if by_name[sn]["category"] == "Component" or d.get("treatAsComponentForRepairs"):
            recipe = by_name[sn].get("crafting", {}).get("ingredients", [])
            component_costs[sn] = recipe[0] if recipe else None
    repair_bench = next((t for cs in g.prefabs.values() for cls, _, t in cs if cls == "RepairBench"), {})
    out = {}
    for sn, cs in assets.items():
        rec, definition = {}, cs["ItemDefinition"]
        consumable = cs.get("ItemModConsumable")
        if consumable:
            rec["consumable"] = {
                "amount": consumable["amountToConsume"],
                "effects": [{"type": METABOLISM[e["type"]] if e["type"] < len(METABOLISM) else str(e["type"]),
                             "amount": e["amount"], "seconds": e["time"], "healthThreshold": e["onlyIfHealthLessThan"]} for e in consumable["effects"]],
                "modifiers": consumable["modifiers"],
            }
        if "ItemModFoodSpoiling" in cs:
            food = cs["ItemModFoodSpoiling"]
            rec["spoiling"] = {"hours": food["TotalSpoilTimeHours"]}
            product = g.item(g.items_file.name, food["SpoilItem"])
            if product:
                rec["spoiling"]["item"] = product
        wearable = cs.get("ItemModWearable")
        if wearable:
            armor = g.get(g.items_file.name, wearable["armorProperties"])
            mask = armor[2]["area"] if armor else 0
            rec["wearable"] = {
                "protection": _protection(g, g.items_file.name, wearable["protectionProperties"]),
                "areas": [area for i, area in enumerate(AREAS) if mask & (1 << i)],
                "blocksAiming": bool(wearable["blocksAiming"]),
                "preventsMounting": bool(wearable["preventsMounting"]),
            }
        projectile_mod = next((t for t in cs.values() if "projectileObject" in t and "ammoType" in t), None)
        if projectile_mod:
            prefab = g.guid_path.get(projectile_mod["projectileObject"].get("guid"))
            projectile = next((t for _, _, t in g.prefabs.get(prefab, []) if "damageTypes" in t), {})
            rec["projectile"] = {
                "ammoType": projectile_mod["ammoType"], "count": projectile_mod["numProjectiles"],
                "velocity": projectile_mod["projectileVelocity"], "spread": projectile_mod["projectileSpread"],
                "damage": _damage(projectile.get("damageTypes", [])),
                **_fields(projectile, {"drag": "drag", "gravity": "gravityModifier", "damageDistances": "damageDistances", "damageMultipliers": "damageMultipliers"}),
            }
            radial = cs.get("ItemModProjectileRadialDamage")
            if radial:
                rec["projectile"]["radial"] = {"damage": _damage([radial["damage"]]), "radius": radial["radius"],
                                               "ignoreHitObject": bool(radial["ignoreHitObject"]), "onlyDoors": bool(radial["onlyDoors"])}
        condition = definition["condition"]
        if condition["enabled"]:
            rec["condition"] = {"repairable": bool(condition["repairable"]), "found": {
                "min": condition["foundCondition"]["fractionMin"], "max": condition["foundCondition"]["fractionMax"]}}
        if condition["repairable"] and by_name[sn].get("crafting"):
            refill = cs.get("ItemModRepair", {})
            rec["repair"] = {
                "ingredients": [] if refill.get("canUseRepairBench") else repair_ingredients(by_name[sn]["crafting"]["ingredients"], component_costs),
                "costFraction": 0.2,
                "maxConditionLost": repair_bench.get("maxConditionLostOnRepair", 0.2),
            }
            if refill:
                rec["repair"]["refill"] = {"workbench": refill["workbenchLvlRequired"], "conditionLost": refill["conditionLost"],
                                           "canUseRepairBench": bool(refill["canUseRepairBench"])}
        rec["despawn"] = {"quick": bool(definition["quickDespawn"]), "rarity": definition["despawnRarity"]}
        for cls, _, t in g.prefabs.get(by_name[sn].get("entity"), []):
            if "primaryMagazine" in t:
                magazine = t["primaryMagazine"]["definition"]
                rec["weapon"] = {"class": cls, "magazine": magazine["builtInSize"], "ammoTypes": magazine["ammoTypes"],
                                  **_fields(t, {"repeatDelay": "repeatDelay", "reloadTime": "reloadTime", "deployDelay": "deployDelay",
                                               "damageScale": "damageScale", "velocityScale": "projectileVelocityScale", "aimCone": "aimCone",
                                               "hipAimCone": "hipAimCone", "automatic": "automatic", "fractionalReload": "fractionalReload",
                                               "reloadStart": "reloadStartDuration", "reloadFraction": "reloadFractionDuration", "reloadEnd": "reloadEndDuration"})}
            if "gathering" in t:
                rec["gathering"] = {kind.lower(): _fields(t["gathering"][kind], {"damage": "gatherDamage", "destroyFraction": "destroyFraction", "conditionLost": "conditionLost"}) for kind in ("Tree", "Ore", "Flesh")}
            if "damageTypes" in t and "maxDistance" in t:
                rec["melee"] = {"damage": _damage(t["damageTypes"]), "deployableDamage": _damage(t.get("deployableDamageOverrides", [])),
                                 "range": t["maxDistance"], "repeatDelay": t["repeatDelay"]}
            if "healDurationSelf" in t:
                rec["medical"] = _fields(t, {"selfSeconds": "healDurationSelf", "otherSeconds": "healDurationOther", "reviveSeconds": "healDurationOtherWounded"})
            if "inputs" in t and "outputs" in t:
                fields = _fields(t, {"maxOutput": "maxOutput", "capacityWattSeconds": "maxCapactiySeconds", "chargeEfficiency": "chargeRatio",
                                    "maximumInboundEnergyRatio": "maximumInboundEnergyRatio", "solarMaxOutput": "maximalPowerOutput",
                                    "windMaxOutput": "maxPowerGeneration", "generatorOutput": "electricAmount", "fuelOutput": "outputEnergy",
                                    "fuelPerSecond": "fuelPerSec", "consumption": "powerConsumption"})
                rec["electrical"] = {"class": cls, **fields}
        out[sn] = rec
    return dict(sorted(out.items()))
