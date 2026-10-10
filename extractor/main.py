"""Extract Rust game data from the game's bundles.

Usage: python extractor/main.py <server_dir> <client_dir> <out_dir>

server_dir: a RustDedicated download containing Bundles/ (anonymous)
client_dir: Rust client Bundles/shared/{items.preload,textures.*}.bundle (account that owns Rust)
"""

import json
import sys
from pathlib import Path

import items as items_mod
import raid
import world
from game import Game
import monuments


def write(out: Path, name: str, data):
    (out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def main(server: Path, client: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    g = Game(server, client)

    records = items_mod.extract(g, out)
    write(out, "items.json", records)

    rarity = {r["shortname"]: r["rarity"] for r in records}
    write(out, "techtree.json", world.techtree(g, rarity))
    write(out, "monuments.json", monuments.extract(g))
    write(out, "recyclers.json", world.recyclers(g))
    write(out, "loot.json", world.loot(g))
    write(out, "vending.json", world.vending(g))

    blocks = raid.building(g)
    deploys = raid.deployables(g, {r["shortname"]: r["entity"] for r in records if "entity" in r})
    booms = raid.explosives(g, g.items())
    write(out, "building.json", blocks)
    write(out, "explosives.json", booms)
    write(out, "raid.json", raid.raid(blocks, deploys, booms))

    print(
        f"{len(records)} items ({sum('io' in r for r in records)} with IO, {sum('icon' in r for r in records)} icons), "
        f"{len(blocks)} building blocks, {len(deploys)} raidable deployables, {len(booms)} explosives"
    )


if __name__ == "__main__":
    main(*(Path(a) for a in sys.argv[1:4]))
