# Demiurge — Implementation Plan

This file tracks milestones, design decisions, and current progress.
The project constitution (philosophy, iron laws, architecture constraints) lives in PROJECT_GUIDE.md.

---

## Milestones

### Milestone 0: Project Structure Design
**Status:** In progress

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
│   └── recording.py   # data recording interface stub (law 6)
├── render/            # rendering/input — pygame lives only here (laws 1,2,4)
│   ├── renderer.py    # draws from pure snapshot data
│   └── input.py       # mouse click -> selected-agent logic state
└── demiurge/          # creator intervention channel
    └── interventions.py  # read/edit any agent's genes; create agent from given genes
```

---

### Milestone 1: Core Loop
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

- Predator decision rule (v1): move toward nearest significantly smaller agent; random walk if no target. Body size difference threshold TBD.
- Sexual reproduction interface must be designed to be swappable from milestone 1.
