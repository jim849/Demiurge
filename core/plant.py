"""Plant: a discrete, stationary food source.

Design decisions (see PLAN.md, Milestone 1):
- **Discrete entity, not a grid cell.** Each plant is its own object with an id,
  so it slots straight into the existing id-based targeting: a brain emits
  `EatAction(target_id)` and the world resolves that id against either the plant
  or the agent table. This matches `PerceivedPlant` (id + body_radius) already in
  the decision contract.
- **Immutable.** A v1 plant is eaten whole (instantaneous, no partial grazing), so
  its fields never change after birth -- it is created, perceived, and removed.
  Frozen + slotted: cheap and safe to share into snapshots without copying.
- **`energy` is the food value** transferred (scaled by the eater's herbivory
  efficiency) when consumed. It is world-internal -- brains judge a plant by their
  own `plant_gain`, so `energy` is deliberately NOT exposed in `PerceivedPlant`.
- **`body_radius`** gives plants the same contact geometry as agents: reach is the
  sum of the two body radii.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.vector import Vector


@dataclass(frozen=True, slots=True)
class Plant:
    """One plant: where it is, how big its contact disc is, and its food value."""

    id: int
    position: Vector
    body_radius: float
    energy: float

    def __post_init__(self) -> None:
        if self.body_radius <= 0:
            raise ValueError("plant body_radius must be positive")
        if self.energy <= 0:
            raise ValueError("plant energy must be positive")


@dataclass(frozen=True, slots=True)
class PlantParams:
    """Tunable plant-economy coefficients (instantiated from config, iron law 10).

    `regen_per_tick` new plants are scattered each tick until the world holds
    `max_count`. A fixed-rate, hard-capped model: simple and, because regrowth runs
    every tick, the food supply can never be permanently grazed to zero (PLAN's
    "can't be eaten to zero in one pass"). A density-dependent (logistic) rate is a
    candidate refinement later.
    """

    energy: float
    body_radius: float
    regen_per_tick: int
    max_count: int

    def __post_init__(self) -> None:
        if self.energy <= 0:
            raise ValueError("plant energy must be positive")
        if self.body_radius <= 0:
            raise ValueError("plant body_radius must be positive")
        if self.regen_per_tick < 0:
            raise ValueError("regen_per_tick cannot be negative")
        if self.max_count < 0:
            raise ValueError("max_count cannot be negative")
