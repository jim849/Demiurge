"""The creator intervention channel (the Demiurge's hands on the world).

Deliberately a SEPARATE top-level package from `core/` (see PLAN.md, Milestone 0):
manual intervention is the *creator's* tool, not a simulation rule. The core must
never depend on this package; this package depends on the core. Keeping it out of
`core/` means the simulation can run with zero interventions and stays honest about
what is emergent vs. what was hand-placed.
"""
