# rust-items-json

Item data for [Rust](https://rust.facepunch.com/), extracted straight from the game files every week.

Every item has its id, shortname, name, description, category, stack size and condition, plus:

- **`icon`**: the in-game inventory icon (256×256 WebP), decoded from the game's own textures.
- **`io`**: wiring for anything with power, water or industrial connections: each input and output slot with its name, type (`electric`, `fluid`, `industrial`) and 3D position on the model.
- **`crafting`**: ingredients, amount, craft time, workbench level, research cost.
- **`recycle`**: scrap from recycling.
- **`entity`**: the prefab the item places or spawns.

Everything is keyed by item `id` and `shortname`.

## Use it

```
https://raw.githubusercontent.com/bobosneefdev/rust-items-json/master/data/items.json
https://raw.githubusercontent.com/bobosneefdev/rust-items-json/master/data/icons/<shortname>.webp
```

`data/meta.json` has the Rust build id the data came from (`build`), when it last changed (`updated`) and when it was last checked (`checked`).

```json
{
  "id": -1448252298,
  "shortname": "electrical.branch",
  "name": "Electrical Branch",
  "category": "Electrical",
  "io": {
    "class": "ElectricalBranch",
    "ioType": "electric",
    "inputs": [{ "name": "Power In", "type": "electric", "position": [0, -0.12, 0.03] }],
    "outputs": [
      { "name": "Power Out", "type": "electric", "position": [-0.03, 0.13, 0.03] },
      { "name": "Branch Out", "type": "electric", "position": [0.03, 0.13, 0.03] }
    ]
  },
  "crafting": { "ingredients": [{ "item": "metal.fragments", "amount": 75 }], "amount": 1, "time": 30, "workbench": 1, "...": "..." },
  "icon": "icons/electrical.branch.webp"
}
```

## How it updates

A GitHub Action runs every **Thursday at 12:07 Los Angeles time** (Rust's patch day), with a backup run Friday at the same time. It checks the current Rust build and only re-extracts when it changed:

1. Downloads the dedicated server bundles (anonymous) and the client's item and texture bundles (needs an account that owns Rust) with [DepotDownloader](https://github.com/SteamRE/DepotDownloader).
2. Reads them with [UnityPy](https://github.com/K0lb3/UnityPy). Bundles are read by byte range, so the 6–7 GB texture bundles never load into memory.
3. Commits the result.

### Run it yourself

```sh
uv sync
# needs STEAM_USERNAME, STEAM_PASSWORD, STEAM_SHARED_SECRET for the client bundles
DD=/path/to/DepotDownloader scripts/fetch.sh
uv run extractor/extract.py game/server game/client/Bundles/shared data
```

## License

The extraction code is MIT. The data and icons are from Rust and belong to Facepunch Studios. This project is not affiliated with or endorsed by Facepunch.
