import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { lootProbabilities } from "../dist/index.js";

const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(readFileSync(new URL(`../../data/${url.split("/data/")[1]}`, import.meta.url), "utf8")) });

test("loot probabilities include matching reverse item sources", async () => {
  const stats = await lootProbabilities({ fetch });
  const source = stats.items["rifle.ak"].find((s) => s.container.endsWith("/codelockedhackablecrate.prefab"));
  assert.ok(source.chance > 0.28 && source.chance < 0.29);
  assert.equal(stats.containers[source.container].find((d) => d.item === "rifle.ak").chance, source.chance);
});
