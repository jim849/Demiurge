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
    body_radius_unit=10.0,
    base_rest=0.0,
    metab_cost_coeff=1.0,
    vision_cost_coeff=1.0,
    vision_half_angle_min=0.25,
    vision_half_angle_max=math.pi,
    vision_range_unit=100.0,
    vision_range_exponent=0.5,
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
        "size": 0.5, "speed": 0.5, "vision_budget": 0.5, "vision_focus": 0.5,
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


def test_panoramic_focus_gives_full_circle_field_of_view():
    # focus=0 -> half-angle = max (pi) -> cos(pi) = -1 -> every direction visible.
    p = express(_genome(vision_focus=0.0), _P)
    assert p.perception_half_angle == pytest.approx(math.pi)
    assert p.perception_cos_half_angle == pytest.approx(-1.0)


def test_higher_focus_narrows_the_cone():
    wide = express(_genome(vision_focus=0.2), _P)
    narrow = express(_genome(vision_focus=0.9), _P)
    assert narrow.perception_half_angle < wide.perception_half_angle


def test_concentrating_the_same_budget_reaches_farther():
    # Same visual budget, narrower focus -> higher receptor density -> longer range.
    wide = express(_genome(vision_budget=0.5, vision_focus=0.0), _P)
    narrow = express(_genome(vision_budget=0.5, vision_focus=1.0), _P)
    assert narrow.perception_range > wide.perception_range


def test_cannot_be_cheaply_wide_and_far():
    # A panoramic prey and a telephoto predator on the SAME budget pay the SAME
    # resting cost, yet the predator out-ranges the wide-eyed prey.
    prey = express(_genome(vision_budget=0.5, vision_focus=0.0), _P)
    predator = express(_genome(vision_budget=0.5, vision_focus=1.0), _P)
    assert prey.resting_cost == pytest.approx(predator.resting_cost)
    assert predator.perception_range > prey.perception_range


def test_body_radius_proportional_to_size_gene():
    small = express(_genome(size=0.2), _P)
    big = express(_genome(size=0.8), _P)
    assert small.body_radius == pytest.approx(2.0)
    assert big.body_radius == pytest.approx(8.0)


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
    # Hold visual budget equal so we isolate the size*metabolism contribution.
    lean = express(_genome(size=0.2, metabolism=0.2, vision_budget=0.1), _P)
    heavy = express(_genome(size=0.9, metabolism=0.9, vision_budget=0.1), _P)
    assert heavy.resting_cost > lean.resting_cost


def test_larger_visual_budget_costs_resting_energy():
    small = express(_genome(vision_budget=0.1), _P)
    large = express(_genome(vision_budget=0.9), _P)
    assert large.resting_cost > small.resting_cost


def test_vision_cost_is_independent_of_focus():
    # Reshaping the field is free: only total budget costs.
    a = express(_genome(vision_budget=0.5, vision_focus=0.1), _P)
    b = express(_genome(vision_budget=0.5, vision_focus=0.9), _P)
    assert a.resting_cost == pytest.approx(b.resting_cost)


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


# --- eating willingness (B': probability tracks digestibility) ----------------

def test_pure_specialists_have_extreme_eat_probabilities():
    herb = express(_genome(diet=0.0), _P)
    assert herb.plant_eat_prob == pytest.approx(1.0)
    assert herb.prey_eat_prob == pytest.approx(0.0)
    carn = express(_genome(diet=1.0), _P)
    assert carn.prey_eat_prob == pytest.approx(1.0)
    assert carn.plant_eat_prob == pytest.approx(0.0)


def test_more_carnivorous_means_less_likely_to_eat_plants():
    grazer = express(_genome(diet=0.3), _P)
    hunter = express(_genome(diet=0.7), _P)
    assert hunter.plant_eat_prob < grazer.plant_eat_prob
    assert hunter.prey_eat_prob > grazer.prey_eat_prob


def test_eat_probabilities_are_valid_probabilities():
    for diet in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = express(_genome(diet=diet), _P)
        assert 0.0 <= p.plant_eat_prob <= 1.0
        assert 0.0 <= p.prey_eat_prob <= 1.0


def test_eat_prob_equals_normalized_gain():
    p = express(_genome(diet=0.4), _P)
    assert p.plant_eat_prob == pytest.approx(p.plant_gain / _P.herb_max)
    assert p.prey_eat_prob == pytest.approx(p.prey_gain / _P.carn_max)


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
