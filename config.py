"""Central configuration: all tunable parameters live here (iron law 10).

Nothing in the simulation should hardcode a tunable number; it should read it
from this module. This file will grow as more systems come online (world size,
energy economy, plant regrowth, ...). For now it holds the genome schema.

Gene values are kept as abstract, mostly-normalized numbers; translating them
into real abilities (and any non-linear curves / trade-offs) is the job of
phenotype.py, not this schema.
"""

from __future__ import annotations

from core.genome import ChromosomeSpec, GeneSpec
from core.phenotype import PhenotypeParams

# --- mutation defaults -------------------------------------------------------
# Kept small for stability (large mutation = chaotic, never converges).
# Body genes mutate slowly; brain/personality genes may drift a bit faster.
_BODY_STEP = 0.02
_LIFE_STEP = 0.03
_BRAIN_STEP = 0.05
_MUT_PROB = 0.10  # per-gene, per-reproduction probability

# --- genome schema: 10 genes across 3 function-grouped chromosomes -----------
# Chromosome grouping is itself a (future) research knob; size+speed are placed
# on the same chromosome so they are linked by default once recombination exists.

GENOME_SCHEMA: tuple[ChromosomeSpec, ...] = (
    ChromosomeSpec(
        name="body",
        genes=(
            GeneSpec("size", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
            GeneSpec("speed", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
            GeneSpec("sense_range", 0.1, 1.0, _BODY_STEP, _MUT_PROB),
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
    # Metabolism / perception
    base_rest=0.1,
    metab_cost_coeff=0.5,
    sense_rest_coeff=0.3,
    sense_unit=100.0,
    # Reproduction
    repro_min=50.0,
    repro_max=200.0,
    # Diet: carnivory peak higher than herbivory; exponents >1 sharpen niches
    herb_max=1.0,
    carn_max=1.5,
    herb_exp=1.5,
    carn_exp=1.5,
)

# --- reproducibility ---------------------------------------------------------
DEFAULT_SEED = 20260609
