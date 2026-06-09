"""Tests for core.phenotype.

Focus on the encoded trade-offs ("no free lunch") and on the genotype/phenotype
separation (re-expression after a gene change).
"""

import math

import pytest

from core.genome import Genome
from core.phenotype import PhenotypeParams, Phenotype, express
import config


# A simple, easy-to-reason-about params set for unit tests.
_P = PhenotypeParams(
    speed_unit=10.0,
    move_cost_coeff=1.0,
    speed_cost_exponent=2.0,
    base_rest=0.0,
    metab_cost_coeff=1.0,
    sense_rest_coeff=1.0,
    sense_unit=100.0,
    repro_min=50.0,
    repro_max=150.0,
    herb_max=1.0,
    carn_max=1.5,
    herb_exp=1.5,
    carn_exp=1.5,
)


def _genome(**overrides) -> Genome:
    """Build a full-schema genome with given gene values (defaults to mid-range)."""
    base = {
        "size": 0.5, "speed": 0.5, "sense_range": 0.5,
        "diet": 0.5, "repro_threshold": 0.5, "metabolism": 0.5,
        "offspring_investment": 0.5,
        "aggression": 0.5, "fear": 0.5, "exploration": 0.5,
    }
    base.update(overrides)
    return Genome.from_values(config.GENOME_SCHEMA, base)


# --- basic mapping -----------------------------------------------------------

def test_max_speed_proportional_to_speed_gene():
    slow = express(_genome(speed=0.2), _P)
    fast = express(_genome(speed=0.8), _P)
    assert fast.max_speed == pytest.approx(4 * slow.max_speed)


def test_max_speed_is_size_neutral_in_v1():
    small = express(_genome(speed=0.5, size=0.2), _P)
    big = express(_genome(speed=0.5, size=0.9), _P)
    assert small.max_speed == big.max_speed


def test_perception_radius_tracks_sense_gene():
    p = express(_genome(sense_range=0.3), _P)
    assert p.perception_radius == pytest.approx(30.0)


# --- trade-offs --------------------------------------------------------------

def test_move_cost_is_super_linear():
    p = express(_genome(size=0.5), _P)
    # exponent 2 -> doubling speed quadruples cost
    assert p.move_cost(4.0) == pytest.approx(4 * p.move_cost(2.0))


def test_bigger_body_costs_more_to_move():
    small = express(_genome(size=0.2), _P)
    big = express(_genome(size=0.9), _P)
    assert big.move_cost(3.0) > small.move_cost(3.0)


def test_bigger_and_higher_metabolism_drains_more_at_rest():
    # Hold perception equal so we isolate the size*metabolism contribution.
    lean = express(_genome(size=0.2, metabolism=0.2, sense_range=0.1), _P)
    heavy = express(_genome(size=0.9, metabolism=0.9, sense_range=0.1), _P)
    assert heavy.resting_cost > lean.resting_cost


def test_wider_perception_costs_resting_energy():
    narrow = express(_genome(sense_range=0.1), _P)
    wide = express(_genome(sense_range=0.9), _P)
    assert wide.resting_cost > narrow.resting_cost


# --- diet single-axis trade-off ----------------------------------------------

def test_pure_herbivore_gets_plant_peak_no_prey():
    p = express(_genome(diet=0.0), _P)
    assert p.plant_gain == pytest.approx(_P.herb_max)
    assert p.prey_gain == pytest.approx(0.0)


def test_pure_carnivore_gets_prey_peak_no_plant():
    p = express(_genome(diet=1.0), _P)
    assert p.prey_gain == pytest.approx(_P.carn_max)
    assert p.plant_gain == pytest.approx(0.0)


def test_generalist_is_penalized_on_both_sides():
    # With exponent 1.5, a 0.5 generalist gets less than half of each peak.
    p = express(_genome(diet=0.5), _P)
    assert p.plant_gain < 0.5 * _P.herb_max
    assert p.prey_gain < 0.5 * _P.carn_max


def test_carnivory_peak_exceeds_herbivory_peak():
    assert _P.carn_max > _P.herb_max


# --- reproduction threshold mapping ------------------------------------------

def test_repro_threshold_maps_normalized_to_energy():
    assert express(_genome(repro_threshold=0.0), _P).repro_threshold_energy == pytest.approx(50.0)
    assert express(_genome(repro_threshold=1.0), _P).repro_threshold_energy == pytest.approx(150.0)
    assert express(_genome(repro_threshold=0.5), _P).repro_threshold_energy == pytest.approx(100.0)


def test_offspring_investment_passthrough():
    assert express(_genome(offspring_investment=0.37), _P).offspring_investment == pytest.approx(0.37)


# --- immutability & re-expression --------------------------------------------

def test_phenotype_is_immutable():
    p = express(_genome(), _P)
    with pytest.raises(Exception):
        p.max_speed = 99.0  # type: ignore[misc]


def test_reexpression_after_gene_change():
    # Simulates a creator edit / future radiation: change a gene, re-express.
    g = _genome(size=0.2)
    before = express(g, _P)
    g.set("size", 0.9)
    after = express(g, _P)
    assert after.move_cost(3.0) > before.move_cost(3.0)


# --- real config params sanity ----------------------------------------------

def test_expresses_with_real_config_params():
    p = express(_genome(), config.PHENOTYPE_PARAMS)
    assert isinstance(p, Phenotype)
    assert p.max_speed > 0
    assert p.repro_threshold_energy > 0
