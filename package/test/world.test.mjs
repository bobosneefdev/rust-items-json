import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { world } from "../dist/index.js";

const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(readFileSync(new URL(`../../data/${url.split("/data/")[1]}`, import.meta.url), "utf8")) });
const data = await world({ fetch });

test("world entities include harvesting and vehicle fuel settings", () => {
  const bear = data.entities["assets/rust.ai/agents/bear/bear.prefab"];
  assert.equal(bear.type, "animal");
  assert.equal(bear.health, 325);
  assert.ok(bear.harvest.some((pool) => pool.items.some((item) => item.item === "leather")));
  assert.ok(Object.values(data.entities).some((entity) => entity.type === "vehicle" && entity.fuelPerSecond > 0));
});

test("scientist loot includes reverse item sources and valid table references", () => {
  assert.ok(data.sources["rifle.ak"].some((source) => source.entity.includes("scientist")));
  const gen2 = Object.keys(data.drops).find((prefab) => prefab.endsWith("/scientist2.heavy.prefab"));
  assert.ok(gen2);
  for (const container of Object.values(data.loot.containers)) {
    for (const slot of container.slots ?? []) assert.ok(data.loot.tables[slot.table]);
  }
});
