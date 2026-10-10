import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { itemProperties } from "../dist/index.js";

const fetch = async (url) => ({ ok: true, json: async () => JSON.parse(readFileSync(new URL(`../../data/${url.split("/data/")[1]}`, import.meta.url), "utf8")) });

test("gameplay properties resolve weapon, medical and armor references", async () => {
  const props = await itemProperties({ fetch });
  assert.equal(props["rifle.ak"].weapon.magazine, 30);
  assert.equal(props["syringe.medical"].consumable.effects.find((e) => e.type === "health").amount, 15);
  assert.equal(props.hazmatsuit.wearable.areas.length, 7);
  assert.ok(props.hazmatsuit.wearable.protection.amounts.bullet > 0.29);
  assert.equal(props["electric.battery.rechargable.large"].electrical.maxOutput, 100);
});
