"""Central configuration: all tunable parameters live here (iron law 10).

Nothing in the simulation should hardcode a tunable number; it should read it
from this module. This file will grow as more systems come online (world size,
energy economy, plant regrowth, ...). For now it holds the genome schema.

Gene values are kept as abstract, mostly-normalized numbers; translating them
into real abilities (and any non-linear curves / trade-offs) is the job of
phenotype.py, not this schema.
"""

from __future__ import annotations

import math

from core.decision.rule_based import BrainParams
from core.genome import ChromosomeSpec, GeneSpec
from core.phenotype import PhenotypeParams
from core.plant import PlantParams
from core.world import PredationParams

# --- mutation defaults -------------------------------------------------------
# Kept small for stability (large mutation = chaotic, never converges).
# Body genes mutate slowly; brain/personality genes may drift a bit faster.
_BODY_STEP = 0.02
_LIFE_STEP = 0.03
_BRAIN_STEP = 0.05
_MUT_PROB = 0.10  # per-gene, per-reproduction probability

# --- genome schema: 11 genes across 3 function-grouped chromosomes -----------
# Chromosome grouping is itself a (future) research knob; size+speed are placed
# on the same chromosome so they are linked by default once recombination exists.
#
# Vision is two genes (a fixed-budget trade-off, not two free abilities):
#   vision_budget = total visual investment (its energy cost is linear);
#   vision_focus  = how that budget is spread -- 0 = panoramic & short-range
#                   (prey eyes), 1 = narrow & long-range (predator eyes).
# Reshaping the field is free; only total budget costs. So an agent CANNOT be
# cheaply wide AND far (see phenotype.py for the curve).

GENOME_SCHEMA: tuple[ChromosomeSpec, ...] = (
    ChromosomeSpec(
        name="body",
        genes=(
            GeneSpec("size", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
            GeneSpec("speed", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
            GeneSpec("vision_budget", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
            GeneSpec("vision_focus", 0.0, 1.0, _BODY_STEP, _MUT_PROB),
        ),
    ),
    ChromosomeSpec(
        name="metabolism",
        genes=(
            GeneSpec("diet", 0.0, 1.0, _LIFE_STEP, _MUT_PROB),
            GeneSpec("repro_threshold", 0.0, 1.0, _LIFE_STEP, _MUT_PROB),
            GeneSpec("metabolism", 0.1, 1.0, _LIFE_STEP, _MUT_PROB),
            GeneSpec("offspring_investment", 0.0, 1.0, _LIFE_STEP, _MUT_PROB),
        ),
    ),
    ChromosomeSpec(
        name="brain",
        genes=(
            GeneSpec("aggression", 0.0, 1.0, _BRAIN_STEP, _MUT_PROB),
            GeneSpec("fear", 0.0, 1.0, _BRAIN_STEP, _MUT_PROB),
            GeneSpec("exploration", 0.0, 1.0, _BRAIN_STEP, _MUT_PROB),
        ),
    ),
)

# --- phenotype mapping coefficients ------------------------------------------
# Curve SHAPES live in core/phenotype.py; these tunable COEFFICIENTS live here
# (iron law 10). All values are starting points, to be tuned by observation.
PHENOTYPE_PARAMS = PhenotypeParams(
    # Movement
    speed_unit=10.0,
    move_cost_coeff=0.5,
    speed_cost_exponent=2.0,
    # Body: world-space radius at size=1 (contact = sum of radii; also the draw size)
    body_radius_unit=10.0,
    # Metabolism
    base_rest=0.1,
    metab_cost_coeff=0.5,
    # Vision (fixed-budget trade-off; see phenotype.express)
    vision_cost_coeff=0.3,        # resting drain per unit visual budget (linear)
    vision_half_angle_min=0.25,   # radians; narrowest cone half-angle (focus=1, ~28° FOV)
    vision_half_angle_max=math.pi,  # radians; widest (focus=0, full panoramic)
    vision_range_unit=60.0,       # range scale (world units)
    vision_range_exponent=0.5,    # range grows as density**this; 0.5 = sqrt (gentle)
    # Reproduction
    repro_min=50.0,
    repro_max=200.0,
    # Diet: carnivory peak higher than herbivory; exponents >1 sharpen niches
    herb_max=1.0,
    carn_max=1.5,
    herb_exp=1.5,
    carn_exp=1.5,
)

# --- rule-based brain knobs --------------------------------------------------
# Thresholds for the hand-written v1 brain (core/decision/rule_based.py). All
# starting points, to be tuned by observation.
BRAIN_PARAMS = BrainParams(
    carnivore_threat_threshold=0.5,  # diet >= this => a neighbour reads as a predator
    predation_size_ratio=1.2,        # need > 1.2x the target's size to prey on it
    fear_flee_distance_unit=100.0,   # flee within (fear * 100) world units of a threat
    cruise_speed_fraction=0.5,       # foraging / wander travel speed (TEMP; see BrainParams)
)

# --- plants (food) -----------------------------------------------------------
# Discrete plant entities; energy is the food value transferred (scaled by the
# eater's herbivory efficiency) when one is consumed whole. Starting points,
# to be tuned by observation.
INITIAL_PLANT_COUNT = 400  # plants scattered at world setup
PLANT_PARAMS = PlantParams(
    energy=30.0,        # food value of one plant
    body_radius=3.0,    # world-space radius (contact = sum of body radii)
    regen_per_tick=4,   # new plants scattered each tick (fixed-rate regrowth)
    max_count=600,      # hard cap on living plants (regrowth stops here)
)

# --- predation (world-authoritative) -----------------------------------------
# The World's own copy of the rules it uses to ADJUDICATE a kill, deliberately
# separate from the brain's belief (BRAIN_PARAMS.predation_size_ratio): the brain
# proposes, the world disposes. In v1 size_ratio matches the brain's value.
PREDATION_PARAMS = PredationParams(
    size_ratio=1.2,         # predator size must exceed 1.2x the prey's size to kill
    body_value_coeff=0.3,   # structural meal value = coeff * body_radius**2 (area~mass)
)

# --- reproduction ------------------------------------------------------------
# v1 asexual (copy + mutate); the strategy module is wired in by the caller
# (main.py / tests), not here. This is the one placement knob the World needs:
# offspring are born within OFFSPRING_PLACEMENT_FACTOR * parent body_radius, kept
# tight so neighbours tend to be kin (population viscosity -> kin-selection substrate).
OFFSPRING_PLACEMENT_FACTOR = 2.0

# --- reproducibility ---------------------------------------------------------
DEFAULT_SEED = 20260609
