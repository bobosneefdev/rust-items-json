# rust-items-json

Game data for [Rust](https://rust.facepunch.com/), extracted straight from the game files every week. Nothing is scraped from other sites or entered by hand.

| File | What's in it |
| --- | --- |
| `data/items.json` | Every item: id, shortname, name, description, category, stack size, rarity, condition, plus **IO wiring**, **crafting**, **research cost** and **recycling yield** |
| `data/icons/<shortname>.webp` | The in-game inventory icon (256×256), decoded from the game's own textures |
| `data/techtree.json` | Workbench tech trees: nodes, unlock paths and scrap costs |
| `data/recyclers.json` | Recycler tiers (green, yellow, red): efficiency, speed, powergrid bonuses |
| `data/loot.json` | Loot containers (barrels, crates, airdrops...) and the weighted loot tables they roll |
| `data/loot-probabilities.json` | Per-container drop chances, expected quantities, possible totals, condition ranges, and reverse item-to-container lookup |
| `data/vending.json` | NPC shops (outpost, bandit camp, fishing villages): what they sell and for how much |
| `data/building.json` | Building blocks per grade: health, cost, damage protection, soft-side protection |
| `data/explosives.json` | Everything that explodes: damage by type and blast radius |
| `data/raid.json` | How many of each explosive destroys each building block, door and wall, hard and soft side |
| `data/combat.json` | Target protections and damage primitives for weapon/ammo combinations, melee, thrown projectiles and explosions |
| `data/meta.json` | The Rust build the data came from, when it last changed and when it was last checked |
| `CHANGELOG.md` | What changed in each Rust update |

Everything is keyed by item `shortname` (and `id` in `items.json`), so files join cleanly.

## Use it

### JavaScript / TypeScript

```sh
npm install rust-items-json
```

```ts
import { items, raid, iconUrl } from "rust-items-json";

const all = await items(); // fully typed
const branch = all.find((i) => i.shortname === "electrical.branch");
branch?.io?.outputs; // [{ name: "Power Out", type: "electric", position: [...] }, ...]
iconUrl(branch!); // https://raw.githubusercontent.com/.../icons/electrical.branch.webp

// Pin to a Rust build instead of tracking the latest:
await raid({ ref: "build-25824447" });
```

### Anything else

```
https://raw.githubusercontent.com/bobosneefdev/rust-items-json/master/data/items.json
https://raw.githubusercontent.com/bobosneefdev/rust-items-json/master/data/icons/<shortname>.webp
```

Each Rust update is also published as a [release](https://github.com/bobosneefdev/rust-items-json/releases) tagged `build-<id>`, with the full `data/` folder attached as a zip.

## Notes on the data

- **IO positions** are 3D plug positions on the model, in metres.
- **Recycling** yields are per item at efficiency 1.0. Multiply by a recycler's `efficiency` from `recyclers.json` (green 0.5, yellow 0.4, red 0.75). Fractions are rolled as chances in game.
- **Research and tech tree costs** are vanilla, without server tax. Tech trees marked `"vanilla": false` only appear on primitive-era or game-mode servers.
- **Raid counts** assume every hit lands at the centre of the blast, follow the game's damage pipeline (`BaseCombatEntity.Hurt`), and use vanilla server settings. `soft` is listed only when the soft side takes more damage.
- **Combat** preserves damage per hit and target protections, including hard-side attributes on child GameObjects. `combat()`, `raidDamage()`, `raidHits()` and `raidPlan()` support weapon-specific damage, current health, soft sides and ordered mixed attacks. `rawMaterialCost()` expands crafting recipes into per-unit materials, excluding craft-batch rounding and weapon acquisition. Timing estimates assume full magazines and uninterrupted attacks; unavailable/fractional-reload timings return null. Damage assumes point-blank hits without attachments, splash obstruction, fire ticks, skills, special entity overrides or server modifiers. Explosion distance falloff is available through `raidDamage(..., blastDistance)`; fire-producing items describe impact damage only.
- **Loot**: a table either spawns all its `items` (amount in [min, max]) or picks one weighted sub-table. A container rolls each of its `slots` (`rolls` times at `chance`), or its `table` `rolls` times.
- **Loot probabilities** model vanilla table rolls before inventory-capacity limits and game-mode modifiers. `chance` means at least one item; `expectedAmount` includes unsuccessful rolls. Rust rolls varying amounts as floats and truncates them to integers, so raw table maxima differ from possible integer totals. `refresh` is contents refresh, not monument/entity respawn. Condition ranges apply to roadside/town loot; other container types receive full condition.

## How it updates

A GitHub Action checks the Rust build every **six hours** and re-extracts after build changes, extractor changes merged into master, or a forced manual run:

1. Downloads the dedicated server bundles (anonymous) and the client's item and texture bundles (an account that owns Rust) with [DepotDownloader](https://github.com/SteamRE/DepotDownloader).
2. Reads them with [UnityPy](https://github.com/K0lb3/UnityPy). Bundles are read by byte range, so the 6–7 GB texture bundles never load into memory.
3. Writes the changelog, commits, and publishes a release.

### Run it yourself

```sh
uv sync
# needs STEAM_USERNAME, STEAM_PASSWORD, STEAM_SHARED_SECRET for the client bundles
DD=/path/to/DepotDownloader scripts/fetch.sh
uv run extractor/main.py game/server game/client/Bundles/shared data
```

## License

The extraction code and npm package are MIT. The data and icons are from Rust and belong to Facepunch Studios. This project is not affiliated with or endorsed by Facepunch.
