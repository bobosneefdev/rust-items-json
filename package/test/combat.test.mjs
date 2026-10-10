import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { combat, raidDamage, raidHits, raidPlan, rawMaterialCost } from "../dist/index.js";

const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(readFileSync(new URL(`../../data/${url.split("/data/")[1]}`, import.meta.url), "utf8")) });
const data = await combat({ fetch });
const wallId = Object.keys(data.targets).find((id) => id.endsWith("/wall/wall.prefab#stone"));
const wall = data.targets[wallId];

test("explosive ammo includes weapon damage and child hard-side protection", () => {
  const attack = data.attacks["rifle.semiauto:ammo.rifle.explosive"];
  assert.equal(raidHits(wall, attack), 185);
  assert.ok(raidDamage(wall, attack, "soft") > raidDamage(wall, attack, "hard"));
  assert.ok(raidHits(wall, data.attacks["hatchet:melee"], wall.health, "soft") < raidHits(wall, data.attacks["hatchet:melee"]));
});

test("partial health and mixed plans consume only the required remainder", () => {
  assert.equal(raidHits(wall, data.attacks["explosive.timed:blast"], 200), 1);
  const plan = raidPlan(data, wallId, [{ attack: "explosive.timed:blast", count: 1 }, { attack: "ammo.rocket.basic:blast", count: 10 }]);
  assert.equal(plan.destroyed, true);
  assert.deepEqual(plan.consumed, [{ item: "explosive.timed", amount: 1 }, { item: "ammo.rocket.basic", amount: 2 }]);
  assert.throws(() => raidPlan(data, wallId, [{ attack: "explosive.timed:blast", count: -1 }]), RangeError);
  assert.throws(() => raidHits(wall, data.attacks["explosive.timed:blast"], NaN), RangeError);
});

test("distance falloff and immunity are explicit", () => {
  const attack = data.attacks["ammo.rocket.basic:blast"];
  assert.equal(raidDamage(wall, attack, "hard", attack.radius), 0);
  assert.equal(raidHits(wall, { item: "test", kind: "melee", damage: { heat: 10 } }), null);
});

test("recursive material expansion accounts for recipe output quantities", () => {
  const items = JSON.parse(readFileSync(new URL("../../data/items.json", import.meta.url), "utf8"));
  const costs = rawMaterialCost(items, [{ item: "explosive.timed", amount: 2 }]);
  assert.equal(costs.find((c) => c.item === "sulfur").amount, 4400);
  assert.throws(() => rawMaterialCost(items, [{ item: "missing", amount: 1 }]), /unknown item/);
});
