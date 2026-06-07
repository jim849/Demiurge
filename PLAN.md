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
- *(to be filled as decisions are made)*

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
