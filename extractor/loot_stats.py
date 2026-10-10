"""Exact marginal loot-roll probabilities, independent of inventory capacity/server modifiers."""

import math


def _amount(lo, hi):
    if not 0 <= lo <= hi:
        raise ValueError(f"invalid loot amount range: {lo}, {hi}")
    if hi == lo:
        n = math.floor(lo)
        return {"chance": float(n > 0), "expectedAmount": n, "min": n, "max": n}

    # ItemAmountRanged.GetAmount rolls a float; LootSpawn truncates it to an integer.
    def integral(x):
        n = math.floor(x)
        return n * (n - 1) / 2 + n * (x - n)

    return {
        "chance": max(0, min(1, (hi - max(lo, 1)) / (hi - lo))),
        "expectedAmount": (integral(hi) - integral(lo)) / (hi - lo),
        "min": math.floor(lo),
        "max": math.ceil(hi) - 1,
    }


def _repeat(stats, rolls, chance=1):
    if not isinstance(rolls, int) or rolls < 0 or not 0 <= chance <= 1:
        raise ValueError("invalid loot rolls or chance")
    return {item: {
        "chance": 1 - (1 - chance * s["chance"]) ** rolls,
        "expectedAmount": chance * rolls * s["expectedAmount"],
        "min": rolls * s["min"] if chance == 1 else 0,
        "max": rolls * s["max"] if chance > 0 else 0,
    } for item, s in stats.items()}


def _combine(parts):
    out = {}
    for part in parts:
        for item, s in part.items():
            if item not in out:
                out[item] = dict(s)
            else:
                prev = out[item]
                prev["chance"] = 1 - (1 - prev["chance"]) * (1 - s["chance"])
                for key in ("expectedAmount", "min", "max"):
                    prev[key] += s[key]
    return out


def calculate(loot, conditions=None):
    tables, cache, visiting = loot["tables"], {}, set()

    def table(name):
        if name in cache:
            return cache[name]
        if name in visiting:
            raise ValueError(f"cyclic loot table: {name}")
        if name not in tables:
            raise ValueError(f"unknown loot table: {name}")
        visiting.add(name)
        raw = tables[name]
        picks = [p for p in raw.get("pick", []) if p["weight"] > 0]
        if any(p["weight"] < 0 for p in raw.get("pick", [])):
            raise ValueError(f"negative loot weight: {name}")
        if picks:
            total = sum(p["weight"] for p in picks)
            choices = [(p["weight"] / total, _repeat(table(p["table"]), 1 + p.get("extra", 0))) for p in picks]
            result = {}
            for item in {item for _, stats in choices for item in stats}:
                entries = [(weight, stats.get(item, {"chance": 0, "expectedAmount": 0, "min": 0, "max": 0})) for weight, stats in choices]
                result[item] = {
                    "chance": sum(w * s["chance"] for w, s in entries),
                    "expectedAmount": sum(w * s["expectedAmount"] for w, s in entries),
                    "min": min(s["min"] for _, s in entries),
                    "max": max(s["max"] for _, s in entries),
                }
        else:
            result = _combine({i["item"]: _amount(i["min"], i["max"])} for i in raw.get("items", []))
        visiting.remove(name)
        cache[name] = result
        return result

    containers, items = {}, {}
    for prefab, container in sorted(loot["containers"].items()):
        slots = container.get("slots") or [{"table": container["table"], "rolls": container.get("rolls", 1), "chance": 1}]
        stats = _combine(_repeat(table(s["table"]), s["rolls"], s["chance"]) for s in slots)
        if container.get("scrap"):
            stats = _combine([stats, {"scrap": _amount(container["scrap"], container["scrap"])}])
        drops = []
        for item, s in sorted(stats.items()):
            if s["chance"] <= 0:
                continue
            rec = {"item": item, **s}
            if conditions and item in conditions:
                rec["condition"] = conditions[item] if container["type"] in {"town", "roadside"} else {"min": 1, "max": 1}
            drops.append(rec)
            items.setdefault(item, []).append({"container": prefab, **{k: v for k, v in rec.items() if k != "item"}})
        containers[prefab] = drops
    return {"containers": containers, "items": dict(sorted(items.items()))}
