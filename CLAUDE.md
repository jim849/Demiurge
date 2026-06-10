# Demiurge — Claude Code Instructions

## Project overview
Artificial life / evolution simulation. See PROJECT_GUIDE.md for the full constitution.
See PLAN.md for current milestone and progress.

## How to run
```bash
# headless: run the simulation and print periodic population stats
python main.py                       # 1000 ticks, default seed
python main.py --ticks 5000 --every 250
python main.py --seed 7

# windowed: open a pygame view (space=pause, .=step, up/down=speed, q=quit)
python main.py --render
```
Dependencies: runtime in `requirements.txt` (pygame-ce), dev in
`requirements-dev.txt` (pytest). The repo venv is `eden_venv/`; run via
`eden_venv/bin/python` (bare `python` may be unavailable).

## Language conventions
- **Conversation:** Chinese
- **All project code, comments, filenames, identifiers, commits:** English

## Architecture iron laws (summary — full version in PROJECT_GUIDE.md §8)
1. Simulation core must have zero `pygame` imports — logic and rendering are completely separate.
2. Rendering module consumes pure data snapshots from the core.
3. Positions use vector representation, not scattered `x, y` variables.
4. Mouse selection belongs to the rendering/input layer; "which agent is selected" is a logic state — keep them cleanly separated.
5. Decision, gene, reproduction, and attribute systems must all be replaceable modules.
6. Stub data recording interfaces from day one (don't implement, just leave clean hooks).
7. Fixed random seed for reproducibility; update order must be deterministic.
8. RNG dependency injection — never use module-global `random` in the core; pass an RNG instance explicitly.
9. Core must be testable headless (no pygame/graphics in the core — a benefit of law 1).
10. All tunable parameters in a single config file — never hardcoded.
11. Use `pathlib` for all file paths; no platform-specific separators.

## File responsibilities (keep separate)
- **PROJECT_GUIDE.md** — constitution: philosophy, constraints, iron laws. Stable.
- **PLAN.md** — milestone roadmap + decision/progress log. Update as work progresses.
- **README.md** — human-facing: what it is + how to run (GitHub front page; create later).
- **CLAUDE.md** — this file: conventions Claude auto-loads.

## Git workflow
- Commit after each confirmed milestone step.
- Commit messages in English, imperative mood.
- Push to remote after each milestone (M0, M1, ...) completes.
- Never force-push.
