# Ecology Tuning Experiments — Carnivore Viability

Detailed log of the parameter-tuning experiments behind the M1 decision-log entry
**"Niche differentiation: carnivory cannot emerge gradually"** in PLAN.md.
PLAN.md holds the conclusions; this file holds the raw runs and the seed morphs
used to test them, so the main progress log stays uncluttered.

Method: edit `config.py` → run a headless `main.py` (5000–30000 ticks) → inspect
the diet / size distributions with a throwaway `/tmp` script
(`PYTHONPATH=/Users/ashitaka/Desktop/Demiurge eden_venv/bin/python ...`).
"measure, don't assume."

---

## Parameter → result chain

Each row is cumulative (the change is kept into the next row unless noted).

| # | Change | Observed outcome |
|---|---|---|
| 1 | `move_cost_coeff` 0.5 → 0.25 | No visible effect; diet still collapses to ~0.01 (pure-herbivore monoculture). |
| 2 | + concave diet curve `herb_exp=carn_exp=0.75` | diet stabilizes at ~0.31 — a single **omnivore** species; still **no carnivores**. |
| 3 | + Kleiber `metab_size_exponent=0.75` (economy of scale) | Breaks the collapse dynamic; diet stays stable ~0.31. |
| 4 | + world 1000 → 400 | size explodes to the ceiling 1.0 — **large-herbivore monoculture**; plants overgrazed to ~20; the 1.2× predation gate locks predation out. |
| 5 | + predation `size_ratio` 1.2 → 1.1 (brain + world) | diet climbs then plateaus at ~0.1; still **no carnivores**. |
| 6 | + convex diet curve `herb_exp=carn_exp=1.5` | Empties the mid-diet band (disruptive selection confirmed), but **every lineage slides to the herbivore peak**; the carnivore peak is never populated (max diet ≤0.29 over 20000 ticks). |

Representative tails (full logs were transient task outputs):

- Convex run, 30000 ticks: `final diet hist: [568, 0, 0, 0, 0, 0, 0, 0, 0, 0]` — all 568 agents in the lowest diet bin, `carn(>=.6)=0`.
- Concave/omnivore run, 20000 ticks: `final diet hist: [10, 145, 46, 0, ...]`, diet mean ~0.17–0.20, `carn(>=.6)=0`.

---

## Seeding experiments (coherent morphs)

`populate()` already spreads diet 0..1 (independent uniform per-gene draws), but
genes are **uncorrelated** — a carnivore-diet individual gets a random (usually
too-small) size, so no viable predator morph exists at t0. To test whether a
*coherent* predator is viable at all, we seeded designed morphs via
`spawn_agent(genome, ...)`.

**Two morphs used (gene dicts, for reproduction):**

```python
CARN = dict(
    diet=0.9, size=0.9, speed=0.7,
    vision_budget=0.8, vision_focus=0.35,
    aggression=0.9, fear=0.1,
    metabolism=0.4, repro_threshold=0.4, offspring_investment=0.4,
    exploration=0.6,
)
HERB = dict(
    diet=0.1, size=0.35, speed=0.3,
    vision_budget=0.4, vision_focus=0.5,
    aggression=0.2, fear=0.7,
    metabolism=0.4, repro_threshold=0.4, offspring_investment=0.4,
    exploration=0.4,
)
```

**Findings:**

1. A coherently-seeded carnivore (`CARN`) **is viable and powerful** — it feasts
   and reproduces explosively once placed among herbivores.
2. The hard part is **predator–prey balance**, a narrow band bracketed on both sides:
   - **Too-fast breeding** → overshoot crash. A single ~107-energy kill instantly
     exceeds the repro threshold ("eat one = breed one") → exponential predator
     growth → prey wiped out in ~15 ticks → predators starve → total extinction
     (seen at t46–66). This looked like a bug; fine-grained diagnostics showed it
     was a genuine Lotka–Volterra crash.
   - **Too-slow breeding** → predators starve out. With carnivore
     `repro_threshold` raised to ~192 energy (gene 0.95) and herbivore lowered to
     ~65 (gene ~0.1), seeded 270 herb : 30 carn, the carnivores died before
     t1000 and herbivores thrived to 568. (See the bracketing run below.)

**Bracketing run (slow-breeder carnivores, over-corrected):**

```
carn repro_thresh=192  herb repro_thresh=65
seeded: herb=270(fast breeder) : carn=30(slow breeder)
t  1000 n= 182 herb= 182 ... carn= 0
...
t 30000 n= 568 herb= 568 ... carn= 0
final diet hist: [568, 0, ...]  carn(>=.6): 0
```

Coexistence lives between this and the overshoot crash — a balance-tuning target,
not an emergence problem.

---

## Config changes that came out of these experiments

Kept as a sound rebalance even where they didn't by themselves produce carnivores
(see PLAN.md decision log for the rationale):

- `PHENOTYPE_PARAMS.move_cost_coeff`: 0.5 → **0.25**
- `PHENOTYPE_PARAMS.metab_size_exponent`: **0.75** (new — Kleiber economy of scale)
- `PHENOTYPE_PARAMS.herb_exp / carn_exp`: **1.5** (convex — disruptive-selection prerequisite)
- `WORLD_SIZE`: 1000×1000 → **400×400** (with `SPATIAL_CELL_SIZE` 100 → 50)
- `BRAIN_PARAMS.predation_size_ratio`: 1.2 → **1.1**
- `PREDATION_PARAMS`: the hard `size_ratio=1.1` gate was later **replaced** by a
  probabilistic kill (see the next section); the brain still keeps its 1.1 belief.

---

## Toward coexistence: three mechanisms, and why boom-bust is the realistic floor

After the morphs above confirmed that seeded carnivores are viable but always
crash, we added three mechanisms (each its own commit), prioritising **realism**.
All are headless-measured on the seeded run (`--seed-morph`, seed 20260609).

**① Conservative assimilation** (`carn_max` 1.5→1.0, `herb_max` 1.0→0.8): a meal can
only lose energy in transfer, never multiply it. Removed the "meat creates energy"
source; the herbivore base now survives instead of the whole system dying.

**② Size-scaled reproduction cost**: `repro_threshold_energy` gains
`repro_size_cost_coeff * body_radius**2` (an offspring is a body; biomass ~size²,
the same shape as the predation meal). Carnivore threshold 110 → ~207, so one kill
(80→151) no longer triggers a birth — a reproductive lag that brakes the "eat one =
breed one" overshoot. The r/K difference now *emerges* from the size gene.

**③ Probabilistic predation (replaces the hard size gate)**: kill probability is a
logistic on the log size-ratio `r = hunter/prey`,
`p = 1/(1+(midpoint/r)**steepness)` (midpoint 1.3, steepness 4.0). Carnivore vs
herbivore (r~2.6) ≈ 0.94; equal size ≈ 0.26; a smaller hunter still ≈ 0.08 (never 0).
Contested prey resolves in two stages: each in-contact hunter rolls its own chance
(a swarm is harder to escape), then the carcass goes to one success drawn ∝ size.

**④ Holling II handling time**: a kill starts a `handling_time`-tick digesting
cooldown during which the predator can't kill again — caps each predator's kill rate.

**Combined effect (seed 20260609, 270 herb : carn seeded):**

| stage | outcome |
|---|---|
| before (hard gate, carn_max 1.5) | total extinction, fast |
| ①+②+③ | total-extinction → **predator boom-bust + herbivore recovery** |
| +④ handling_time=10 | predator persistence ~tick 154 → **~335** (≈2×) |

**Sweeps that came up empty (no stable coexistence):**

- `repro_size_cost_coeff` ∈ {1.2…6.0} × carn0 {30,15}, 3000 ticks: only shifts
  carnivore death time ~150→~240; coeff too high (6.0) → total extinction
  (over-hunts without breeding). **Wrong knob** — repro cost changes *how many*
  predators, not *how fast* they deplete prey.
- `handling_time` ∈ {0…30} × carn0 {30,15}: best is H≈10 (death ~335); higher H
  kills predators *earlier* (can't feed). Caps kill rate but can't stop the
  in-sync crash.
- World size at constant density (`s` = 1,2,3,4; H=10): death 335 → 822 (s=2) then
  **saturates** (817, 733 at s=3,4). Bigger space helps, but uniform seeding +
  identical dynamics keep all patches *in phase* — no spatial asynchrony, so no
  metapopulation rescue.

**Conclusion.** The mechanisms are correct and realistic, and they turn total
collapse into a boom-bust with prey recovery — itself a valid ecological outcome.
But **stable predator-prey coexistence does not fall out of parameter tuning**: a
well-mixed system collapses in sync (cf. Huffaker's mite experiments — coexistence
needed spatial structure + asynchrony). Sustained coexistence is therefore deferred
to a later spatial/resource-patch milestone, not chased with config knobs now.
M1's bar — the world is *alive and evolving* — is met (herbivores persist and
generations advance).
