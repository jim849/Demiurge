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
- `PREDATION_PARAMS.size_ratio`: 1.2 → **1.1**
