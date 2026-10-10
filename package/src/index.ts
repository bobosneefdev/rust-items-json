// Typed access to rust-items-json. The data lives in the GitHub repo and is fetched on demand,
// so the package stays tiny and always matches the latest Rust build (or a pinned one).

export type Shortname = string;

export type IoType = "electric" | "fluid" | "kinetic" | "generic" | "industrial";

export interface IoSlot {
  name: string;
  type: IoType;
  /** Plug position on the 3D model, in metres: [x, y, z]. */
  position: [number, number, number];
}

export interface Io {
  /** Game component class, e.g. "ElectricalBranch". */
  class: string;
  ioType: IoType;
  inputs: IoSlot[];
  outputs: IoSlot[];
}

export interface ItemAmount {
  item: Shortname;
  amount: number;
}

export interface Crafting {
  ingredients: ItemAmount[];
  /** Items produced per craft. */
  amount: number;
  /** Craft time in seconds. */
  time: number;
  /** Workbench level required (0 = none). */
  workbench: number;
  craftable: boolean;
  researchable: boolean;
  defaultBlueprint: boolean;
  /** Scrap to research at a research table (vanilla). */
  researchScrap?: number;
}

export interface Item {
  id: number;
  shortname: Shortname;
  name: string;
  description: string;
  category: string;
  stackable: number;
  rarity: string | null;
  hidden: boolean;
  condition: { enabled: boolean; max: number };
  /** Prefab the item places or spawns. */
  entity?: string;
  io?: Io;
  crafting?: Crafting;
  /** Yield per item at recycler efficiency 1.0; multiply by a recycler's `efficiency`. */
  recycle?: ItemAmount[];
  /** Path relative to the data root, e.g. "icons/rifle.ak.webp" (256×256). */
  icon?: string;
}

export interface ItemProperties {
  consumable?: { amount: number; effects: { type: string; amount: number; seconds: number; healthThreshold: number }[];
    modifiers: { type: number; source: number; value: number; duration: number }[] };
  spoiling?: { hours: number; item?: Shortname };
  wearable?: { protection: Protection | null; areas: string[]; blocksAiming: boolean; preventsMounting: boolean };
  projectile?: { ammoType: number; count: number; velocity: number; spread: number; damage: Partial<Record<DamageType, number>>;
    drag?: number; gravity?: number; damageDistances?: { x: number; y: number }; damageMultipliers?: { x: number; y: number };
    radial?: { damage: Partial<Record<DamageType, number>>; radius: number; ignoreHitObject: boolean; onlyDoors: boolean } };
  condition?: { repairable: boolean; found: { min: number; max: number } };
  /** Multiply ingredients by costFraction * (1 - condition / maxCondition), then ceil each amount. */
  repair?: { ingredients: ItemAmount[]; costFraction: number; maxConditionLost: number;
    refill?: { workbench: number; conditionLost: number; canUseRepairBench: boolean } };
  /** Asset settings; actual timers depend on server convars and contained items. */
  despawn: { quick: boolean; rarity: number };
  weapon?: { class: string; magazine: number; ammoTypes: number; repeatDelay?: number; reloadTime?: number; deployDelay?: number;
    damageScale?: number; velocityScale?: number; aimCone?: number; hipAimCone?: number; automatic?: number;
    fractionalReload?: number; reloadStart?: number; reloadFraction?: number; reloadEnd?: number };
  gathering?: Record<"tree" | "ore" | "flesh", { damage: number; destroyFraction: number; conditionLost: number }>;
  melee?: { damage: Partial<Record<DamageType, number>>; deployableDamage: Partial<Record<DamageType, number>>; range: number; repeatDelay: number };
  medical?: { selfSeconds?: number; otherSeconds?: number; reviveSeconds?: number };
  electrical?: { class: string; maxOutput?: number; capacityWattSeconds?: number; chargeEfficiency?: number;
    maximumInboundEnergyRatio?: number; solarMaxOutput?: number; windMaxOutput?: number; generatorOutput?: number;
    fuelOutput?: number; fuelPerSecond?: number; consumption?: number };
}

export interface Recycler {
  type: "green" | "yellow" | "red";
  efficiency: number;
  seconds: number;
  powergrid: { requiredStage: number; efficiencyStage: number; efficiency: number; durationStage: number; seconds: number };
}

export interface TechTreeNode {
  id: number;
  inputs: number[];
  outputs: number[];
  item?: Shortname;
  /** Scrap to unlock this node (vanilla, no tax). */
  scrap?: number;
  group?: string;
}

export interface TechTree {
  name: string;
  workbench: 1 | 2 | 3;
  /** Shown on vanilla servers. */
  vanilla: boolean;
  eras: string[];
  nodes: TechTreeNode[];
}

export interface LootTable {
  /** Every item spawns, with an amount in [min, max]. */
  items?: { item: Shortname; min: number; max: number }[];
  /** Or one weighted sub-table is picked (repeated `1 + extra` times). */
  pick?: { table: string; weight: number; extra?: number }[];
}

export interface LootContainer {
  /** Contents refresh interval in seconds; not the monument's entity respawn interval. */
  refresh?: { min: number; max: number } | null;
  initialLootSpawn?: boolean;
  destroyOnEmpty?: boolean;
  type: "generic" | "player" | "town" | "airdrop" | "crashsite" | "roadside";
  class: string;
  /** Each slot rolls `rolls` times, spawning its table with probability `chance`. */
  slots?: { table: string; rolls: number; chance: number; loadout?: string }[];
  /** Used when there are no slots: the table is spawned `rolls` times. */
  table?: string;
  rolls?: number;
  /** Scrap added on top of the rolled loot. */
  scrap?: number;
}

export interface Loot {
  containers: Record<string, LootContainer>;
  tables: Record<string, LootTable>;
}

export interface LootProbability {
  /** Probability of receiving at least one, 0..1. */
  chance: number;
  expectedAmount: number;
  /** Possible total amount including zero; varying float quantities are truncated by Rust. */
  min: number;
  max: number;
  /** Fraction of maximum item durability, 0..1. */
  condition?: { min: number; max: number };
}

export interface LootProbabilities {
  containers: Record<string, (LootProbability & { item: Shortname })[]>;
  items: Record<Shortname, (LootProbability & { container: string })[]>;
}

export interface VendingOrder {
  sell: Shortname;
  amount: number;
  currency: Shortname;
  price: number;
  blueprint?: boolean;
  stock?: number;
  randomPrice?: { min: number; max: number };
}

export interface Shop {
  name: string;
  orders: VendingOrder[];
}

export interface WorldEntity {
  type: "animal" | "npc" | "vehicle" | "collectable" | "resource";
  classes: string[];
  name: string;
  health?: number;
  protection?: Protection | null;
  harvest?: { type: string; items: ItemAmount[]; finishBonus: ItemAmount[] }[];
  pickup?: ItemAmount[];
  attacks?: { class: string; damage: Partial<Record<DamageType, number>> }[];
  fuelPerSecond?: number;
  storage?: { class: string; prefab?: string; slots: number }[];
  corpse?: string;
  loot?: string;
  loadouts?: { name: string; items: ItemAmount[]; belt: ItemAmount[]; main: ItemAmount[]; wear: ItemAmount[] }[];
}

export interface WorldDrop {
  chance: number;
  expectedAmount: number;
  min: number;
  max: number;
}

export interface World {
  entities: Record<string, WorldEntity>;
  loot: Loot;
  /** Variants keyed by loadout name; "default" includes only unconditional slots. */
  drops: Record<string, Record<string, (WorldDrop & { item: Shortname })[]>>;
  sources: Record<Shortname, (WorldDrop & { entity: string; loadout?: string })[]>;
}

export type DamageType = string;

export interface Protection {
  name: string;
  /** Fraction of each damage type blocked, -1..1. */
  amounts: Partial<Record<DamageType, number>>;
}

export type Grade = "twig" | "wood" | "stone" | "metal" | "armored";

export interface BuildingBlock {
  prefab: string;
  name: string;
  grades: { grade: Grade; health: number; cost: ItemAmount[]; protection: Protection | null }[];
  /** Extra protection on the hard side; hits on the soft (weak) side skip it. */
  softSide: Protection | null;
}

export interface Explosive {
  item: Shortname;
  prefab?: string;
  class: string;
  /** Damage by type at the centre of the blast. */
  damage: Partial<Record<DamageType, number>>;
  radius: number;
  minRadius: number;
}

export interface RaidTarget {
  protection?: Protection | null;
  softSide?: Protection | null;
  /** Building blocks have prefab + grade; deployables (doors, walls...) have item. */
  prefab?: string;
  grade?: Grade;
  item?: Shortname;
  health: number;
  /** Explosives needed to destroy the target. `soft` is only present when it differs. */
  explosives: Record<Shortname, { hard?: number; soft?: number; hardDamage?: number; softDamage?: number }>;
}

export interface CombatTarget {
  prefab: string;
  item?: Shortname;
  grade?: Grade;
  class: string;
  health: number;
  protection: Protection | null;
  softSide: Protection | null;
  meleeOverride?: boolean;
}

export interface CombatAttack {
  item: Shortname;
  weapon?: Shortname;
  kind: "explosive" | "projectile" | "melee" | "thrown";
  damage: Partial<Record<DamageType, number>>;
  deployableDamage?: Partial<Record<DamageType, number>>;
  radial?: { damage: Partial<Record<DamageType, number>>; radius: number; ignoreHitObject: boolean; onlyDoors: boolean };
  repeatDelay?: number;
  reloadTime?: number;
  magazine?: number;
  fractionalReload?: boolean;
  reloadStart?: number;
  reloadFraction?: number;
  reloadEnd?: number;
  fuse?: { min: number; max: number };
  canStick?: boolean;
  radius?: number;
  minRadius?: number;
}

export interface Combat {
  targets: Record<string, CombatTarget>;
  attacks: Record<string, CombatAttack>;
}

export interface Meta {
  /** Rust client build id the data came from. */
  build: string;
  updated: string;
  checked: string;
}

export interface Files {
  "items.json": Item[];
  "item-properties.json": Record<Shortname, ItemProperties>;
  "recyclers.json": Recycler[];
  "techtree.json": TechTree[];
  "loot.json": Loot;
  "loot-probabilities.json": LootProbabilities;
  "vending.json": Shop[];
  "world.json": World;
  "building.json": BuildingBlock[];
  "explosives.json": Explosive[];
  "raid.json": RaidTarget[];
  "combat.json": Combat;
  "meta.json": Meta;
  "monuments.json": Monuments;
}

export interface MonumentLocation {
  /** Build-local component ID for relationships within this file. */
  id: string;
  path: string;
  position: [number, number, number];
  rotation: [number, number, number, number];
  /** Row-major 3x4 affine transform, including nonuniform scale/shear. */
  matrix: number[];
  active: boolean;
}

export interface MonumentBounds { m_Center: { x: number; y: number; z: number }; m_Extent: { x: number; y: number; z: number } }

export interface Monument {
  name: string;
  type: string;
  tierMask: number;
  bounds: MonumentBounds;
  safeZone: boolean;
  minWorldSize: number;
  allowPatrolHeliCrash: boolean;
  hasDungeonLink: boolean;
  areas: (MonumentLocation & { name: string; bounds: MonumentBounds; safeZone: boolean })[];
  spawns: (MonumentLocation & { class: string; candidates: { prefab: string | null; unresolvedGuid?: string; weight: number; chance: number; mobile: boolean }[];
    populationLimit: number; perTick?: { min: number; max: number }; respawn: { min: number; max: number } | null;
    points: { position: [number, number, number]; class: string; active: boolean }[]; initialSpawn?: boolean;
    preventDuplicates?: boolean; enabled?: boolean; resetBehavior?: number })[];
  facilities: (MonumentLocation & { class: string; shop?: string })[];
  cameras: (MonumentLocation & { code: string; hasPTZ: boolean })[];
  radiation: (MonumentLocation & { tier: number; amountOverride: number; bypassArmor: boolean; falloff: number;
    colliders: { type: string; Enabled?: boolean; Center?: { x: number; y: number; z: number };
      Size?: { x: number; y: number; z: number }; Radius?: number; Height?: number; Direction?: number }[] })[];
  puzzles: (MonumentLocation & { class: string; accessLevel?: number; accessDuration?: number; timeBetweenResets?: number;
    playersBlockReset?: boolean; scaleWithServerPopulation?: boolean; pauseUntilLooted?: boolean; spawnGroups?: string[];
    resetEntities?: string[]; outputs?: { name: string; target: string; slot: number }[] })[];
  placedEntities: (MonumentLocation & { prefab: string; class: string })[];
}

export interface Monuments {
  monuments: Record<string, Monument>;
  entities: Record<string, { monument: string; spawn?: string; instance?: string; chance?: number }[]>;
  unresolvedSpawns: { monument: string; spawn: string; guid: string; active: boolean }[];
}

export interface Options {
  /** Git ref to read: "master" (latest, default) or a release tag like "build-25824447". */
  ref?: string;
  /** Override the data root URL entirely (e.g. a self-hosted mirror). */
  base?: string;
  fetch?: typeof fetch;
}

const REPO = "https://raw.githubusercontent.com/bobosneefdev/rust-items-json";

export const dataUrl = (path: string, opts: Options = {}): string =>
  `${opts.base ?? `${REPO}/${opts.ref ?? "master"}/data`}/${path}`;

/** URL of an item's 256×256 WebP icon, or undefined when the game has none. */
export const iconUrl = (item: Pick<Item, "icon">, opts: Options = {}): string | undefined =>
  item.icon ? dataUrl(item.icon, opts) : undefined;

export async function load<K extends keyof Files>(file: K, opts: Options = {}): Promise<Files[K]> {
  const res = await (opts.fetch ?? fetch)(dataUrl(file, opts));

  if (!res.ok) throw new Error(`rust-items-json: ${file}: HTTP ${res.status}`);

  return (await res.json()) as Files[K];
}

export const items = (opts?: Options) => load("items.json", opts);

export const itemProperties = (opts?: Options) => load("item-properties.json", opts);

export const recyclers = (opts?: Options) => load("recyclers.json", opts);

export const techtree = (opts?: Options) => load("techtree.json", opts);

export const loot = (opts?: Options) => load("loot.json", opts);

export const lootProbabilities = (opts?: Options) => load("loot-probabilities.json", opts);

export const vending = (opts?: Options) => load("vending.json", opts);

export const world = (opts?: Options) => load("world.json", opts);

export const building = (opts?: Options) => load("building.json", opts);

export const explosives = (opts?: Options) => load("explosives.json", opts);

export const raid = (opts?: Options) => load("raid.json", opts);

export const combat = (opts?: Options) => load("combat.json", opts);

export { raidDamage, raidHits, raidPlan, rawMaterialCost } from "./combat.js";

export const meta = (opts?: Options) => load("meta.json", opts);

export const monuments = (opts?: Options) => load("monuments.json", opts);
