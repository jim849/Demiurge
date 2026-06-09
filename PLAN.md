# Demiurge — Implementation Plan

This file tracks milestones, design decisions, and current progress.
The project constitution (philosophy, iron laws, architecture constraints) lives in PROJECT_GUIDE.md.

---

## Milestones

### Milestone 0: Project Structure Design
**Status:** Complete (design only, no code yet)

Define all files/modules, their responsibilities, and how they interact before writing any functional code.
Must clearly reflect:
- Logic / rendering separation
- Gene system as core data structure
- Replaceable decision module interface
- Manual intervention and creation (Demiurge) interfaces
- Selection interaction layering
- Data recording interface stubs

**Decision log:**
- Doc responsibilities separated: PROJECT_GUIDE (constitution) / PLAN (progress) / README (human-facing run guide, later) / CLAUDE (auto-loaded conventions).
- Added iron law: RNG dependency injection (no module-global `random` in core) to harden reproducibility.
- Added iron law: core must be testable headless (no pygame in core).
- **Brain = phenotype expressed from genes.** The decision-maker is not fixed logic baked into the agent; it is expressed from the agent's genome via the phenotype mapping. Each agent holds its own decision-maker (enables "different individuals, different minds"). v1: rule-based decision whose parameters (aggression, food preference, flee threshold, etc.) are gene-controlled. Future: neural network whose weights are a gene segment on the chromosome — same decision interface, the expression function decodes genes into weights.
- **`demiurge/` is a separate top-level module** (manual intervention is the creator's tool, not a simulation rule).
- **Position uses continuous coordinates** (not a discrete grid). Reason: richer sensory input (distance/angle to targets) to feed individual brains, and smoother path to 3D. Cost accepted: neighbor queries need spatial partitioning (grid buckets).
- **Core agent storage v1 = AoS (Agent objects) behind a `World` access interface.** External code never iterates the agent list directly — it goes through `World` methods. This lets the internal storage be swapped to SoA/NumPy vectorization later without changing callers. Design philosophy: array-thinking at the boundary, AoS inside for v1, interface isolates the two.
- **Snapshot (core → render data) = structured arrays.** Cheap regardless of internal storage; adapts us to array thinking early; serves rendering and future analysis.

**Proposed module structure (tentative, pending build):**
```
Demiurge/
├── main.py            # entry: assemble modules, run loop, connect core <-> render
├── config.py          # all tunable parameters (law 10)
├── requirements.txt
├── core/              # simulation core — zero pygame (law 1)
│   ├── world.py       # World: holds agents/plants, advances one tick, exposes access interface
│   ├── agent.py       # Agent: energy, position, heading, genome, decision-maker
│   ├── genome.py      # chromosome / genes (core data structure)
│   ├── phenotype.py   # genotype -> phenotype mapping (incl. brain expression)
│   ├── vector.py      # vector position/heading (law 3, 3D-ready)
│   ├── rng.py         # RNG instance held & passed explicitly (laws 7, 8)
│   ├── decision/      # replaceable decision module (law 5)
│   │   ├── base.py    # decision-maker interface (ABC)
│   │   └── rule_based.py
│   ├── reproduction/  # replaceable reproduction module (law 5)
│   │   ├── base.py    # reproduction interface: (parent genome, rng) -> child genome
│   │   └── asexual.py # v1: copy + mutate (calls genome.mutate); M3 adds sexual.py
│   └── recording.py   # data recording interface stub (law 6)
├── render/            # rendering/input — pygame lives only here (laws 1,2,4)
│   ├── renderer.py    # draws from pure snapshot data
│   └── input.py       # mouse click -> selected-agent logic state
└── demiurge/          # creator intervention channel
    └── interventions.py  # read/edit any agent's genes; create agent from given genes
```

---

#### Gene System Design (finalized in Milestone 0)

**Design philosophy: no free lunch.** Niches and counter-relationships can only emerge if genes carry costs. The trade-offs live in the genotype→phenotype mapping (`phenotype.py`), NOT in the genes themselves. Mutation only touches genes; balance tuning only touches the mapping.

**Chromosomes (3, function-grouped, assignment is a config knob):**
- **Chromosome 1 — Body:** `size`, `speed`, `sense_range`
- **Chromosome 2 — Metabolism/Life:** `diet`, `repro_threshold`, `metabolism`, `offspring_investment`
- **Chromosome 3 — Brain/Personality:** `aggression`, `fear`, `exploration`

Genome = list of chromosomes from day 1 (chromosome-aware structure), so future sexual recombination + linkage need no restructuring. v1 asexual reproduction copies the whole genome, so chromosome count is mechanically inert now — but `size`+`speed` are deliberately placed on the same chromosome (default **linked**); whether to break that linkage is a research question, adjustable via config in M3.

**Genes (10 total, each record carries: value, valid range [min,max], per-gene mutation step):**

| Gene | Range | Role |
|---|---|---|
| `size` | 0.1–1.0 | core of predation/anti-predation |
| `speed` | 0.1–1.0 | expresses MAX speed cap |
| `sense_range` | 0.1–1.0 | perception radius fed to the brain |
| `diet` | 0.0–1.0 | single continuous axis: 0=pure herbivore, 1=pure carnivore |
| `repro_threshold` | (mapped) | energy needed to split (WHEN to reproduce) |
| `metabolism` | 0.1–1.0 | resting energy drain (combined with size) |
| `offspring_investment` | 0.0–1.0 | fraction of energy given to offspring (HOW MUCH); fission↔budding continuum |
| `aggression` | 0.0–1.0 | tendency to chase smaller agents |
| `fear` | 0.0–1.0 | how early to flee larger agents |
| `exploration` | 0.0–1.0 | random walk vs energy-saving rest when no target |

**Reproduction energy accounting (gene-controlled, r/K selection emerges):** when energy ≥ `repro_threshold` the agent splits (v1: automatic trigger). Offspring receives `offspring_investment × parent_energy`, parent keeps `(1 - offspring_investment) × parent_energy`. Low investment ≈ budding (many cheap weak offspring, r-strategy); ~0.5 ≈ binary fission; high investment ≈ sacrificial (strong offspring, parent risks death, K-strategy). Extreme-low investment is self-punishing (offspring too weak to survive), so "half-split" is a possible *winning* outcome, not a hardcoded rule.

**Phenotype mapping (trade-offs, in `phenotype.py`):**
- **Speed is not a constant.** `speed` gene → max-speed cap. Actual per-tick speed is chosen by the brain per state: moderate cruising while foraging, max speed only when fleeing. Energy cost grows **super-linearly with actual speed** (≈ speed², real-world metabolic analogy), so always-sprinting starves — populations evolve sensible cruising speeds.
- **Size↔speed soft tendency, not hard rule.** `max_speed = f(speed_gene, size)`: larger body tends to lower the max-speed cap, but the `speed` gene still allows "big-yet-agile" individual variation. Not "big = always slow."
- **Sense range costs energy.** Larger `sense_range` → wider view → higher resting drain.
- **Metabolism = f(metabolism gene, size).** Both raise resting energy drain.
- **Diet mapping may be non-linear.** Real-world inspired: carnivory yields more energy per successful meal (prey is energy-dense) but predation has a threshold (needs size advantage) and risk/miss cost; herbivory yields less but is stable and ubiquitous. Tune the curve in `phenotype.py`, never the gene.

**Emergent "who eats whom" (no labels):** When A tries to eat B — (1) *can* it: `A.size` must exceed `B.size` by a config threshold; (2) *will/worth it*: driven by `A.diet` (carnivory motivation) and `A.aggression` (personality). Eating plants scales with `1 - diet`. Predation is never a rule — "wolf eats sheep" is the winning outcome of a (big + carnivorous + aggressive) gene combination under selection.

**Species & color via emergence (not preset labels):** No fixed N species. Appearance is a visual read-out of functional genes, so visually similar ≈ genetically close, and offspring resemble parents:

| Visual channel | Gene |
|---|---|
| Hue (red↔green) | `diet` |
| Radius | `size` |
| Shape (elongated↔round) | `speed` |
| Edge spikes | `aggression` |
| Outline halo | `sense_range` |

Note: because appearance reads functional genes, convergent evolution can make unrelated lineages look alike (real phenomenon, e.g. shark vs dolphin). A neutral lineage marker (to distinguish kinship from convergence) is deferred to M3. "Species" as a mating-boundary mechanism also arrives with sexual reproduction in M3.

**Diversity-maintenance prerequisites (built into world rules, not forced):** plants regenerate (can't be eaten to zero in one pass), predation has a threshold + miss cost, and the world has spatial structure (not a homogeneous soup). These let negative frequency-dependent selection (predator-prey oscillation) emerge. Convergence ("monopoly") remains a legitimate observable outcome.

### Decision (Brain) Design v1 (finalized in Milestone 0)

The brain is a **pure function**: perception in → action out. This input/output interface is fixed now so a future neural network consumes the same inputs and emits the same outputs (decision is a swappable module, iron law 5).

**Perception input** (only within `sense_range`): list of nearby agents (relative position + size), list of nearby plants (relative position), own internal state (current energy).

**Action output**: `move(direction, speed_fraction)` OR `eat(target)`. Reproduction is handled separately (auto-trigger v1).

**Arbitration: priority ladder (method A), top-down, first match wins:**
1. **Flee** — a significantly larger agent in range → move away at max speed. Trigger modulated by `fear` (high fear flees early/far, low fear flees only when close).
2. **Eat** — an edible target adjacent → eat (plant weighted by `1-diet`; prey weighted by `diet` + size advantage).
3. **Hunt/forage** — suitable food in range → move toward nearest at cruising speed; prey-vs-plant choice weighted by `diet` and `aggression`.
4. **Wander/rest** — no target → `exploration` decides random walk vs resting to save energy.

Method A chosen for v1 (interpretable, debuggable, personality genes active throughout). Likely upgrade to **method B (utility scoring)** later — swappable without touching core. Reproduction is auto-triggered in v1 but isolated so it can later become a brain-decided action.

### World / Config Structural Decisions (finalized in Milestone 0)

- **Boundary: toroidal** (wrap-around) — no edge effects, suited to ecological study.
- **Plants: patches of varying size and richness** (config: patch count + size range) — creates resource-rich/poor regions, spatial heterogeneity, forces migration and local arms races.
- **Reproduction energy: gene-controlled split** via `offspring_investment` (see gene table) — fission vs budding emerges, not hardcoded.
- **Numeric starting points (all tunable, tuned by observation later):** world 1000×1000 continuous units; ~300 initial agents with random genomes; plant regen rate + max density per patch; starting energy, super-linear move cost, plant energy value, predation energy = fraction of prey energy; death when energy ≤ 0 or predated; per-gene mutation step (body genes small/slow, brain genes can be larger) + mutation probability; fixed RNG seed; deterministic update order by agent id.

---

## Milestone 1: Core Loop
**Status:** Not started

Get the full cycle running: **energy → move → eat → reproduce → mutate → die**

Completion criteria:
- `python main.py` launches a window
- Agents move, eat, reproduce; population evolves over time
- Click an agent to inspect its chromosome
- Manual gene editing and agent creation available via console/config

---

### Milestone 2: Decision Module Swap
**Status:** Not started

Replace rule-based decision with neural-network-driven decision.
Core engine untouched.

---

### Milestone 3: Sexual Reproduction
**Status:** Not started

Add sexual reproduction as a research variable.
Reproduction logic was designed for this extension from the start.

---

### Milestone 4: Data Recording & Analysis
**Status:** Not started

Implement time-series recording (population counts, mean gene values per tick).
Analyze convergence states: stable coexistence, predator-prey oscillation, monopoly, arms race.

---

## Notes & Open Questions

Deferred to Milestone 1 implementation (design decided, exact placement/values TBD):
- **Selection state ownership**: snapshot carries a "selected" flag, but where the selected-agent logic state lives (on `World` vs `Agent`) is TBD. It is a logic state (iron law 4), set by `render/input.py`, never owned by the render layer.
- **Neighbor-query home**: continuous coordinates need spatial partitioning (grid buckets) for perception/contact. v1 may brute-force O(n²) for a few hundred agents; add a spatial index inside `world.py` later behind the same access interface.
- **Eat contact radius**: continuous space needs an "adjacent enough to eat" radius — add to config starting points.
