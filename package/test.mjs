// Checks the published types against the real data files in ../data (run after extraction).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dataUrl, iconUrl, load } from "./dist/index.js";

const local = (path) => readFileSync(new URL(`../data/${path}`, import.meta.url), "utf8");
const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(local(url.split("/data/")[1])) });

test("loads every data file", async () => {
  for (const f of ["items.json", "recyclers.json", "techtree.json", "loot.json", "vending.json", "building.json", "explosives.json", "raid.json", "meta.json"]) {
    assert.ok(await load(f, { fetch }), f);
  }
});

test("items carry the documented shape", async () => {
  const items = await load("items.json", { fetch });
  const branch = items.find((i) => i.shortname === "electrical.branch");
  assert.equal(branch.io.outputs.length, 2);
  assert.equal(branch.crafting.ingredients[0].item, "metal.fragments");
  assert.equal(iconUrl(branch), dataUrl("icons/electrical.branch.webp"));
});

test("raid costs match well-known values", async () => {
  const raid = await load("raid.json", { fetch });
  const wall = (grade) => raid.find((t) => t.prefab?.endsWith("/wall/wall.prefab") && t.grade === grade).explosives;
  assert.equal(wall("stone")["explosive.timed"].hard, 2);
  assert.equal(wall("metal")["explosive.timed"].hard, 4);
  assert.equal(wall("armored")["explosive.timed"].hard, 8);
  assert.equal(wall("stone")["ammo.rocket.basic"].hard, 4);
});
