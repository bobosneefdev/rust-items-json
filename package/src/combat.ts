import type { Combat, CombatAttack, CombatTarget, Item, ItemAmount, Protection } from "./index.js";

type Side = "hard" | "soft";

function protectedDamage(damage: CombatAttack["damage"], ...protections: (Protection | null)[]): number {
  return Object.entries(damage).reduce((sum, [type, amount]) => sum + protections.reduce(
    (value, protection) => value * (1 - Math.max(-1, Math.min(1, protection?.amounts[type] ?? 0))), amount ?? 0), 0);
}

/** Ideal damage: all projectiles land, point-blank, no attachments/server modifiers/fire ticks. */
export function raidDamage(target: CombatTarget, attack: CombatAttack, side: Side = "hard", blastDistance = 0): number {
  if ((side !== "hard" && side !== "soft") || !Number.isFinite(blastDistance) || blastDistance < 0) throw new RangeError("invalid side or blast distance");
  const directional = side === "hard" ? target.softSide : null;
  const base = attack.kind === "melee" && target.meleeOverride && Object.keys(attack.deployableDamage ?? {}).length
    ? attack.deployableDamage! : attack.damage;
  let damage = protectedDamage(base, target.protection, directional);
  if (attack.kind === "explosive" && attack.radius !== undefined) {
    const min = attack.minRadius ?? 0;
    const factor = attack.radius > min ? 1 - Math.max(0, Math.min(1, (blastDistance - min) / (attack.radius - min))) : Number(blastDistance <= min);
    damage *= factor;
  }
  const radial = attack.radial;
  // ItemModProjectileRadialDamage creates a separate HitInfo without a directional PointStart.
  if (radial && !radial.ignoreHitObject && (!radial.onlyDoors || target.class === "Door")) {
    damage += protectedDamage(radial.damage, target.protection);
  }
  return Math.max(0, damage);
}

function healthFor(target: CombatTarget, health: number): number {
  if (!Number.isFinite(health) || health < 0 || health > target.health) throw new RangeError("health must be between zero and target health");
  return health;
}

/** null means the attack cannot damage the target. */
export function raidHits(target: CombatTarget, attack: CombatAttack, health = target.health, side: Side = "hard"): number | null {
  healthFor(target, health);
  const damage = raidDamage(target, attack, side);
  return health === 0 ? 0 : damage > 0 ? Math.ceil(health / damage - 1e-9) : null;
}

/** Evaluate an ordered mixed plan, consuming only attacks needed before the target dies. */
export function raidPlan(data: Combat, targetId: string, steps: { attack: string; count: number }[], health?: number, side: Side = "hard") {
  const target = data.targets[targetId];
  if (!target) throw new Error(`unknown target: ${targetId}`);
  let remainingHealth = healthFor(target, health ?? target.health);
  const consumed: ItemAmount[] = [], used: { attack: string; count: number }[] = [];
  let seconds: number | null = 0;
  for (const step of steps) {
    const attack = data.attacks[step.attack];
    if (!attack) throw new Error(`unknown attack: ${step.attack}`);
    if (!Number.isSafeInteger(step.count) || step.count < 0) throw new RangeError("attack counts must be nonnegative integers");
    const damage = raidDamage(target, attack, side);
    const count = damage > 0 ? Math.min(step.count, Math.ceil(remainingHealth / damage - 1e-9)) : 0;
    if (count <= 0) continue;
    remainingHealth = Math.max(0, remainingHealth - count * damage);
    used.push({ attack: step.attack, count });
    const existing = consumed.find((item) => item.item === attack.item);
    if (existing) existing.amount += count;
    else consumed.push({ item: attack.item, amount: count });
    if (seconds !== null) {
      if (attack.repeatDelay === undefined || attack.fractionalReload) seconds = null;
      else seconds += (count - 1) * attack.repeatDelay + (attack.magazine ? Math.floor((count - 1) / attack.magazine) * (attack.reloadTime ?? 0) : 0) + (attack.fuse?.max ?? 0);
    }
  }
  return { remainingHealth, destroyed: remainingHealth <= 1e-9, consumed, used, seconds };
}

/** Per-unit recipe expansion; fractional costs exclude craft-batch rounding and weapon costs. */
export function rawMaterialCost(items: Item[], requested: ItemAmount[]): ItemAmount[] {
  const byName = new Map(items.map((item) => [item.shortname, item]));
  const totals = new Map<string, number>();
  function expand(name: string, amount: number, visiting: Set<string>) {
    const item = byName.get(name);
    if (!item) throw new Error(`unknown item: ${name}`);
    if (visiting.has(name)) throw new Error(`cyclic recipe: ${name}`);
    if (!Number.isFinite(amount) || amount < 0) throw new RangeError("amount must be finite and nonnegative");
    const recipe = item.crafting;
    if (recipe?.craftable && recipe.ingredients.length) {
      if (!(recipe.amount > 0)) throw new RangeError("recipe output must be positive");
      const next = new Set(visiting).add(name);
      for (const input of recipe.ingredients) expand(input.item, amount * input.amount / recipe.amount, next);
    } else totals.set(name, (totals.get(name) ?? 0) + amount);
  }
  for (const item of requested) expand(item.item, item.amount, new Set());
  return [...totals].sort(([a], [b]) => a.localeCompare(b)).map(([item, amount]) => ({ item, amount }));
}
