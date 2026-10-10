"""Damage primitives for point-blank projectile, melee, thrown and blast-centre attacks."""

from raid import _damage


def extract(g, records, blocks, deployables, explosives):
    targets, attacks = {}, {}
    for block in blocks:
        for grade in block["grades"]:
            key = block["prefab"] + "#" + grade["grade"]
            targets[key] = {"prefab": block["prefab"], "grade": grade["grade"], "class": "BuildingBlock",
                            "health": grade["health"], "protection": grade["protection"], "softSide": block["softSide"]}
    for target in deployables:
        targets[target["item"]] = {k: target[k] for k in ("item", "prefab", "class", "health", "protection", "softSide", "meleeOverride")}
    items, ammo = g.items(), {}
    for sn, cs in items.items():
        mod = next((t for t in cs.values() if "projectileObject" in t and "ammoType" in t), None)
        if not mod:
            continue
        prefab = g.guid_path.get(mod["projectileObject"].get("guid"))
        projectile = next((t for cls, _, t in g.prefabs.get(prefab, []) if cls == "Projectile"), None)
        if projectile and projectile["damageTypes"]:
            ammo[sn] = mod, projectile, cs.get("ItemModProjectileRadialDamage")
    for item in records:
        sn = item["shortname"]
        for cls, _, t in g.prefabs.get(item.get("entity"), []):
            if "damageTypes" in t and "maxDistance" in t:
                attacks[sn + ":melee"] = {"item": sn, "kind": "melee", "damage": _damage(t["damageTypes"]),
                                           "deployableDamage": _damage(t.get("deployableDamageOverrides", [])), "repeatDelay": t["repeatDelay"]}
            if "primaryMagazine" in t:
                magazine = t["primaryMagazine"]["definition"]
                for ammo_sn, (mod, projectile, radial) in ammo.items():
                    if not magazine["ammoTypes"] & mod["ammoType"]:
                        continue
                    damage = {k: amount * t.get("damageScale", 1) * projectile["damageMultipliers"]["x"] * mod["numProjectiles"]
                              for k, amount in _damage(projectile["damageTypes"]).items()}
                    attack = {"item": ammo_sn, "weapon": sn, "kind": "projectile", "damage": damage,
                              "repeatDelay": t["repeatDelay"], "reloadTime": t["reloadTime"], "magazine": magazine["builtInSize"],
                              "fractionalReload": bool(t["fractionalReload"]),
                              "reloadStart": t["reloadStartDuration"], "reloadFraction": t["reloadFractionDuration"], "reloadEnd": t["reloadEndDuration"]}
                    if radial:
                        attack["radial"] = {"damage": _damage([radial["damage"]]), "radius": radial["radius"],
                                            "ignoreHitObject": bool(radial["ignoreHitObject"]), "onlyDoors": bool(radial["onlyDoors"])}
                    attacks[sn + ":" + ammo_sn] = attack
        if sn in ammo and not ammo[sn][0]["ammoType"]:
            mod, projectile, _ = ammo[sn]
            attacks[sn + ":thrown"] = {"item": sn, "kind": "thrown", "damage": _damage(projectile["damageTypes"])}
    for explosive in explosives:
        sn = explosive["item"]
        # Radial ammunition is represented by weapon+ammo attacks, not a second isolated blast.
        if explosive["class"] == "ItemModProjectileRadialDamage":
            continue
        attack = {"item": sn, "kind": "explosive", "damage": explosive["damage"],
                  "radius": explosive["radius"], "minRadius": explosive["minRadius"]}
        for _, _, t in g.prefabs.get(explosive.get("prefab"), []):
            if "timerAmountMin" in t:
                attack["fuse"] = {"min": t["timerAmountMin"], "max": t["timerAmountMax"]}
                attack["canStick"] = bool(t["canStick"])
        held = next((t for i in records if i["shortname"] == sn for _, _, t in g.prefabs.get(i.get("entity"), []) if "repeatDelay" in t), {})
        if held.get("repeatDelay", 0) > 0:
            attack["repeatDelay"] = held["repeatDelay"]
        attacks[sn + ":blast"] = attack
    return {"targets": dict(sorted(targets.items())), "attacks": dict(sorted(attacks.items()))}
