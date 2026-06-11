"""Genotype -> phenotype mapping: where the "no free lunch" trade-offs live.

Design decisions (see PLAN.md, Milestone 1):
- **Genotype/phenotype separation**: a Genome holds abstract gene values; this
  module translates them into the real abilities the simulation uses. Mutation
  only touches genes; balance tuning only touches this mapping. The two are
  decoupled on purpose.
- **Immutable Phenotype, expressed once**: genes don't change during normal life,
  so a Phenotype is computed at birth and cached. If genes DO change (a creator
  edit, or future radiation), just re-express -- the Phenotype is a frozen value.
- **Engine vs params** (iron law 10): the *shapes* of the curves live here; the
  tunable *coefficients* live in a `PhenotypeParams` object passed in (config.py
  builds the default). This module never imports config, so it stays pure and
  testable with custom params.

Trade-offs encoded (so niches can emerge rather than one super-strategy winning):
- moving costs energy super-linearly in speed (sprinting starves you);
- bigger bodies cost more to move and to maintain (resting metabolism);
- vision is a fixed-budget trade-off: a given visual investment can be spread
  wide (panoramic, short range -- prey eyes) or concentrated (narrow, long range
  -- predator eyes), but not both; only the total budget costs energy, so an
  agent cannot be cheaply wide AND far;
- diet is a single axis: specializing in plants OR prey, never both (carnivory
  has a higher peak yield but you can't also be a good herbivore).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.genome import Genome


@dataclass(frozen=True)
class PhenotypeParams:
    """Tunable coefficients for the genotype->phenotype mapping (lives in config)."""

    # Movement
    speed_unit: float            # max speed at speed_gene = 1 (size-neutral in v1)
    move_cost_coeff: float       # energy per (size * speed^exponent)
    speed_cost_exponent: float   # super-linear; 2.0 = quadratic (metabolic analogy)

    # Body
    body_radius_unit: float      # world-space body radius at size = 1 (drives contact + drawing)

    # Metabolism
    base_rest: float             # baseline resting drain per tick
    metab_cost_coeff: float      # resting drain from metabolism gene, scaled by size
    metab_size_exponent: float   # size scaling of resting metabolism; <1 = Kleiber
                                 # economy of scale (big bodies cheaper per unit)

    # Vision (fixed-budget trade-off: spread wide OR reach far, only budget costs)
    vision_cost_coeff: float       # resting drain per unit visual budget (linear)
    vision_half_angle_min: float   # cone half-angle (radians) at focus = 1 (narrow)
    vision_half_angle_max: float   # cone half-angle (radians) at focus = 0 (panoramic)
    vision_range_unit: float       # range scale (world units)
    vision_range_exponent: float   # range grows as (budget / spread) ** this

    # Reproduction
    repro_min: float             # energy threshold at repro_threshold gene = 0
    repro_max: float             # energy threshold at repro_threshold gene = 1

    # Diet (single axis). Peaks set by *_max; specialization sharpness by *_exp.
    herb_max: float              # peak plant-eating efficiency (pure herbivore)
    carn_max: float              # peak prey-eating efficiency (pure carnivore; > herb_max)
    herb_exp: float              # >1 punishes generalists, sharpening the niche
    carn_exp: float


@dataclass(frozen=True)
class Phenotype:
    """The real abilities an agent uses, derived from its genome. Immutable."""

    size: float
    max_speed: float
    body_radius: float
    perception_range: float          # how far it can see (world units)
    perception_half_angle: float     # cone half-angle (radians); >= pi means panoramic
    perception_cos_half_angle: float # precomputed cos(half_angle) for the visibility test
    resting_cost: float
    repro_threshold_energy: float
    offspring_investment: float
    plant_gain: float
    prey_gain: float
    plant_eat_prob: float        # willingness to ingest a plant, in [0, 1] (= plant_gain / herb_max)
    prey_eat_prob: float         # willingness to ingest prey, in [0, 1]  (= prey_gain / carn_max)

    # Stored so move_cost() can be computed per actual speed each tick.
    _move_cost_factor: float
    _speed_cost_exponent: float

    def move_cost(self, speed: float) -> float:
        """Energy cost of moving at `speed` this tick (super-linear)."""
        return self._move_cost_factor * (speed ** self._speed_cost_exponent)


def express(genome: Genome, params: PhenotypeParams) -> Phenotype:
    """Translate a genome's abstract gene values into a concrete Phenotype."""
    size = genome.get("size")
    speed = genome.get("speed")
    vision_budget = genome.get("vision_budget")
    vision_focus = genome.get("vision_focus")
    diet = genome.get("diet")
    repro_threshold = genome.get("repro_threshold")
    metabolism = genome.get("metabolism")
    offspring_investment = genome.get("offspring_investment")

    # Movement: top speed gene-driven and size-neutral in v1 (inertia/agility is a
    # planned future enhancement). Moving still costs more for bigger bodies.
    max_speed = params.speed_unit * speed
    move_cost_factor = params.move_cost_coeff * size

    # Body radius in world units: drives the contact ("close enough to eat") test
    # (v1 contact = sum of two radii) and rendering. Bigger body = larger reach.
    body_radius = params.body_radius_unit * size

    # Vision: a fixed visual budget can be spread wide (panoramic, short range)
    # or concentrated (narrow, long range), but not both. `vision_focus` sets the
    # cone half-angle (focus=0 -> widest, focus=1 -> narrowest); the same budget
    # spread over a narrower cone gives a higher "receptor density", which reaches
    # farther. Reshaping the field is free -- only the total budget costs energy.
    half_angle = params.vision_half_angle_min + (1.0 - vision_focus) * (
        params.vision_half_angle_max - params.vision_half_angle_min
    )
    spread = half_angle / params.vision_half_angle_max  # in (0, 1], 1 at panoramic
    density = vision_budget / spread
    perception_range = params.vision_range_unit * (density ** params.vision_range_exponent)
    perception_cos_half_angle = math.cos(half_angle)

    # Resting metabolism: bigger + higher-metabolism + larger visual budget drain
    # more. Size scales sub-linearly (Kleiber economy of scale: metab_size_exponent
    # < 1), so large bodies pay less upkeep PER unit -- this, against predation
    # returns that grow with body area (~size**2), is what makes large carnivores
    # pay off. Vision cost is linear in budget only (its SHAPE is free).
    resting_cost = (
        params.base_rest
        + params.metab_cost_coeff * metabolism * (size ** params.metab_size_exponent)
        + params.vision_cost_coeff * vision_budget
    )

    # Reproduction threshold: map normalized gene to a real energy amount.
    repro_threshold_energy = params.repro_min + repro_threshold * (
        params.repro_max - params.repro_min
    )

    # Diet: single axis, non-linear. Can't be good at both (uses diet vs 1-diet).
    plant_gain = params.herb_max * ((1.0 - diet) ** params.herb_exp)
    prey_gain = params.carn_max * (diet ** params.carn_exp)

    # Eating willingness: the same niche curve, normalized to [0, 1], used as the
    # probability of bothering to ingest a food type on contact. The more
    # carnivorous, the less likely to eat a plant it touches (and vice versa), so
    # specialists leave food they can barely digest to those who can.
    plant_eat_prob = (1.0 - diet) ** params.herb_exp
    prey_eat_prob = diet ** params.carn_exp

    return Phenotype(
        size=size,
        max_speed=max_speed,
        body_radius=body_radius,
        perception_range=perception_range,
        perception_half_angle=half_angle,
        perception_cos_half_angle=perception_cos_half_angle,
        resting_cost=resting_cost,
        repro_threshold_energy=repro_threshold_energy,
        offspring_investment=offspring_investment,
        plant_gain=plant_gain,
        prey_gain=prey_gain,
        plant_eat_prob=plant_eat_prob,
        prey_eat_prob=prey_eat_prob,
        _move_cost_factor=move_cost_factor,
        _speed_cost_exponent=params.speed_cost_exponent,
    )
