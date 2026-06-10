"""Rule-based brain: the hand-written v1 decision-maker.

This is the first concrete `DecisionMaker`. It implements a fixed priority ladder
-- Flee > Eat > Hunt/Forage > Wander/Rest -- evaluated top-down each tick; the
first applicable rung produces the action.

Design decisions (see PLAN.md, Decision (Brain) Design v1):
- **Personality is baked in (方案甲).** The brain *is* the expressed phenotype of
  the personality genes (aggression / fear / exploration): they are read from the
  genome once, at `express()`, and stored on the instance. `decide` never reads
  them from Perception -- Perception describes the world and the agent's *body*,
  not its disposition. A future neural-net brain consumes the same Perception and
  emits the same Action, so the engine never changes (iron law 5).
- **Body abilities are read live** from `perception.own_phenotype` (sizes, gains,
  eat probabilities, body radius), because those are the same-for-the-species
  numbers the resolve phase will also use.
- **Pure function, injected RNG** (iron laws 8, and the decide/resolve split):
  `decide` reads a read-only Perception and returns an Action; the only
  stochastic rungs (eat willingness, wander-vs-rest) draw from the passed-in Rng.
- **Brain proposes, world disposes.** Eating only emits `EatAction(target_id)`;
  whether the bite lands (contest, size advantage) is the resolve phase's call.

The tunable thresholds live in a `BrainParams` value object built in config.py
(iron law 10); this module hardcodes no numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.decision.base import (
    Action,
    DecisionMaker,
    EatAction,
    MoveAction,
    Perception,
)
from core.genome import Genome
from core.rng import Rng
from core.vector import Vector


@dataclass(frozen=True)
class BrainParams:
    """Tunable knobs for the rule-based brain (instantiated in config.py)."""

    carnivore_threat_threshold: float  # diet >= this => a neighbour counts as a carnivorous threat
    predation_size_ratio: float        # size advantage requires predator.size > prey.size * this
    fear_flee_distance_unit: float     # flee is triggered within (fear * this) of a threat
    cruise_speed_fraction: float       # foraging / wander speed fraction.
    # NOTE: cruise_speed_fraction is a TEMPORARY rule-brain placeholder. A learning
    # brain (M2) will let each individual settle its own travel speed; only the
    # hand-written brain needs a fixed value, so it lives here rather than as a gene.


class RuleBasedBrain(DecisionMaker):
    """A fixed priority-ladder brain: Flee > Eat > Hunt/Forage > Wander/Rest."""

    __slots__ = ("aggression", "fear", "exploration", "_params")

    def __init__(
        self,
        aggression: float,
        fear: float,
        exploration: float,
        params: BrainParams,
    ) -> None:
        self.aggression = aggression
        self.fear = fear
        self.exploration = exploration
        self._params = params

    @classmethod
    def express(cls, genome: Genome, params: BrainParams) -> "RuleBasedBrain":
        """Build a brain from an agent's genome (mirrors phenotype expression)."""
        return cls(
            aggression=genome.get("aggression"),
            fear=genome.get("fear"),
            exploration=genome.get("exploration"),
            params=params,
        )

    # --- the decision ladder -------------------------------------------------

    def decide(self, perception: Perception, rng: Rng) -> Action:
        flee = self._maybe_flee(perception)
        if flee is not None:
            return flee

        eat = self._maybe_eat(perception, rng)
        if eat is not None:
            return eat

        hunt = self._maybe_hunt_or_forage(perception)
        if hunt is not None:
            return hunt

        return self._wander_or_rest(perception, rng)

    # --- rung 1: flee from a dangerous predator ------------------------------

    def _maybe_flee(self, perception: Perception) -> Action | None:
        """Run from the nearest carnivore big enough to prey on us, if it is close
        enough to scare us. `fear` scales the distance at which we start fleeing."""
        p = self._params
        my_size = perception.own_phenotype.size
        threats = [
            a
            for a in perception.nearby_agents
            if a.diet >= p.carnivore_threat_threshold
            and a.size > my_size * p.predation_size_ratio
        ]
        if not threats:
            return None
        nearest = min(threats, key=lambda a: (a.relative_position.length_squared(), a.id))
        flee_distance = self.fear * p.fear_flee_distance_unit
        if nearest.relative_position.length() > flee_distance:
            return None  # threat seen but still far enough not to bolt
        # Sprint directly away from the nearest threat.
        return MoveAction(direction=-nearest.relative_position, speed_fraction=1.0)

    # --- rung 2: eat something in contact ------------------------------------

    def _maybe_eat(self, perception: Perception, rng: Rng) -> Action | None:
        """If an edible entity is within contact range, maybe bite it. 'Maybe'
        because willingness is probabilistic (B'): the less digestible the food,
        the less likely we bother -- so specialists leave food they can barely use."""
        ph = perception.own_phenotype
        p = self._params
        my_size = ph.size
        my_radius = ph.body_radius

        # (distance_squared, id, eat_probability) for each entity in contact.
        edibles: list[tuple[float, int, float]] = []
        for plant in perception.nearby_plants:
            reach = my_radius + plant.body_radius
            d_sq = plant.relative_position.length_squared()
            if d_sq <= reach * reach:
                edibles.append((d_sq, plant.id, ph.plant_eat_prob))
        for other in perception.nearby_agents:
            if my_size <= other.size * p.predation_size_ratio:
                continue  # no size advantage -> cannot prey on it
            reach = my_radius + other.body_radius
            d_sq = other.relative_position.length_squared()
            if d_sq <= reach * reach:
                edibles.append((d_sq, other.id, ph.prey_eat_prob))

        if not edibles:
            return None
        # Attempt the nearest edible; one willingness roll for its food type.
        _, target_id, eat_prob = min(edibles, key=lambda e: (e[0], e[1]))
        if rng.boolean(eat_prob):
            return EatAction(target_id=target_id)
        return None

    # --- rung 3: go to food (hunt prey / forage plants) ----------------------

    def _maybe_hunt_or_forage(self, perception: Perception) -> Action | None:
        """Pick the higher-utility food type within sight and head for the nearest
        instance of it. Sprint after live prey; cruise toward stationary plants."""
        ph = perception.own_phenotype
        p = self._params
        my_size = ph.size

        huntable = [
            a for a in perception.nearby_agents if my_size > a.size * p.predation_size_ratio
        ]
        prey_value = ph.prey_gain * self.aggression  # aggression = willingness to take the risk
        plant_value = ph.plant_gain

        nearest_prey = (
            min(huntable, key=lambda a: (a.relative_position.length_squared(), a.id))
            if huntable
            else None
        )
        nearest_plant = (
            min(perception.nearby_plants, key=lambda pl: (pl.relative_position.length_squared(), pl.id))
            if perception.nearby_plants
            else None
        )

        prey_option = nearest_prey is not None and prey_value > 0.0
        plant_option = nearest_plant is not None and plant_value > 0.0

        if prey_option and (not plant_option or prey_value >= plant_value):
            return MoveAction(direction=nearest_prey.relative_position, speed_fraction=1.0)
        if plant_option:
            return MoveAction(
                direction=nearest_plant.relative_position,
                speed_fraction=p.cruise_speed_fraction,
            )
        return None

    # --- rung 4: nothing to do -> explore or rest ----------------------------

    def _wander_or_rest(self, perception: Perception, rng: Rng) -> Action:
        """Default behaviour: with probability `exploration`, cruise a random
        direction; otherwise rest in place (speed 0)."""
        heading = perception.own_heading
        if rng.boolean(self.exploration):
            direction = self._random_direction(heading.dim, rng)
            return MoveAction(direction=direction, speed_fraction=self._params.cruise_speed_fraction)
        # Rest: speed 0, so direction is ignored -- keep facing the current heading.
        return MoveAction(direction=heading, speed_fraction=0.0)

    @staticmethod
    def _random_direction(dim: int, rng: Rng) -> Vector:
        """An isotropic random unit vector (Gaussian per component, then normalize).

        Dimension-agnostic: works for 2D now and 3D later without change.
        """
        v = Vector(*(rng.gauss(0.0, 1.0) for _ in range(dim)))
        if v.length_squared() == 0.0:
            # Astronomically unlikely all-zero draw; fall back to a fixed axis.
            return Vector(*([1.0] + [0.0] * (dim - 1)))
        return v.normalized()
