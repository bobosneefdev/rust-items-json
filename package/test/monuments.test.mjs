import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { monuments } from "../dist/index.js";

const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(readFileSync(new URL(`../../data/${url.split("/data/")[1]}`, import.meta.url), "utf8")) });
const data = await monuments({ fetch });

test("Airfield and Oil Rig expose facilities, spawn groups, and camera codes", () => {
  const airfield = data.monuments["assets/bundled/prefabs/autospawn/monument/large/airfield_1.prefab"];
  assert.ok(airfield.facilities.some((facility) => facility.class === "Recycler"));
  assert.ok(airfield.spawns.some((spawn) => spawn.points.length && spawn.candidates.length));
  const rig = data.monuments["assets/bundled/prefabs/autospawn/monument/offshore/oilrig_1.prefab"];
  assert.ok(rig.cameras.some((camera) => camera.code.startsWith("OILRIG")));
});

test("reverse locations and unresolved references point to their monument instances", () => {
  for (const sources of Object.values(data.entities)) {
    for (const source of sources) {
      const monument = data.monuments[source.monument];
      assert.ok(monument);
      assert.ok(source.spawn ? monument.spawns.some((spawn) => spawn.id === source.spawn) : monument.placedEntities.some((instance) => instance.id === source.instance));
    }
  }
  assert.ok(data.unresolvedSpawns.length);
  for (const unresolved of data.unresolvedSpawns) {
    const spawn = data.monuments[unresolved.monument].spawns.find((spawn) => spawn.id === unresolved.spawn);
    assert.ok(spawn.candidates.some((candidate) => candidate.prefab === null && candidate.unresolvedGuid === unresolved.guid && candidate.chance > 0));
  }
});
