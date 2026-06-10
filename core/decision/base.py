"""Decision-maker interface: the fixed contract every "brain" implements.

Design decisions (see PLAN.md, Decision (Brain) Design v1):
- **A brain is a pure function** `decide(perception, rng) -> action`. It reads a
  read-only Perception and returns an Action value; it does NOT mutate the world.
  This fits the simultaneous two-phase tick: every agent decides against the same
  tick-start snapshot (decide phase, zero writes), then the world applies all
  actions together (resolve phase).
- **Swappable (iron law 5).** This contract is fixed now so a future neural
  network (M2) consumes the same Perception and emits the same Action, with no
  change to the core engine. Each agent holds its own DecisionMaker, enabling
  "different individuals, different minds" and (M2 extension) heritable
  rule-vs-NN competition.
- **RNG is injected (iron law 8).** Stochastic choices (e.g. exploration: random
  walk vs rest) must draw from the passed-in Rng, never module-global `random`.
  Deterministic brains may ignore it.
- **Targets are referenced by id, not by object.** Perception entries carry ids,
  and EatAction names a `target_id`. The decide phase only produces ids; the
  resolve phase looks the entity back up. This keeps the snapshot read-only and
  decouples decisions from internal storage (AoS now, SoA later).
- **Relative positions.** Perceived positions are relative to the perceiving
  agent (translation-invariant — friendlier to a future NN and to movement math).

These are immutable value objects (frozen, slotted): cheap to create per agent
per tick, and safe to share without defensive copying.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.phenotype import Phenotype
from core.rng import Rng
from core.vector import Vector


# --- perception (brain input) ------------------------------------------------

@dataclass(frozen=True, slots=True)
class PerceivedAgent:
    """Another agent as seen by the perceiver: identity, where, how big, what it eats.

    `diet` is the *perceived* agent's own diet (0=herbivore .. 1=carnivore). It is
    visible because appearance encodes it (hue = diet), an honest signal: prey can
    tell a predator from a grazer, and a hunter can judge how dangerous a target is.
    """

    id: int
    relative_position: Vector  # target_position - self_position
    size: float
    diet: float


@dataclass(frozen=True, slots=True)
class PerceivedPlant:
    """A plant as seen by the perceiver: identity and where."""

    id: int
    relative_position: Vector


@dataclass(frozen=True, slots=True)
class Perception:
    """Everything a brain is allowed to see this tick (within its sense range).

    Holds only what the brain needs: nearby entities (relative), own energy, and
    own phenotype (so it can reason about its own max_speed / size / reach when
    deciding to chase or flee). Deliberately does NOT expose the whole world.
    """

    nearby_agents: tuple[PerceivedAgent, ...]
    nearby_plants: tuple[PerceivedPlant, ...]
    own_energy: float
    own_phenotype: Phenotype


# --- actions (brain output) --------------------------------------------------

@dataclass(frozen=True, slots=True)
class Action:
    """Base type for a brain's output. Not instantiated directly."""


@dataclass(frozen=True, slots=True)
class MoveAction(Action):
    """Move in `direction` at `speed_fraction` of max speed.

    Only the orientation of `direction` matters (the resolve phase normalizes it);
    its magnitude is ignored. `speed_fraction` in [0, 1] scales max_speed, so
    resting in place is simply `speed_fraction == 0` (no separate rest action).
    """

    direction: Vector
    speed_fraction: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.speed_fraction <= 1.0:
            raise ValueError("speed_fraction must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class EatAction(Action):
    """Attempt to eat the entity named by `target_id` (agent or plant).

    Whether the attempt succeeds (in contact range, size advantage, contest with
    other eaters) is decided by the world's resolve phase, not by the brain.
    """

    target_id: int


# --- the interface -----------------------------------------------------------

class DecisionMaker(ABC):
    """A brain: pure mapping from perception to a single action."""

    @abstractmethod
    def decide(self, perception: Perception, rng: Rng) -> Action:
        """Return the action this agent takes this tick. Must not mutate state."""
        raise NotImplementedError
