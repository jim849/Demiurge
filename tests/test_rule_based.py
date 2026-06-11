"""Tests for core.decision.rule_based — the v1 hand-written brain.

These pin down the priority ladder (Flee > Eat > Hunt/Forage > Wander/Rest),
the 方案甲 split (personality baked into the brain, body read from Perception),
the B' probabilistic eating, and that the brain is a pure, RNG-injected function.
"""

import pytest

from core.decision.base import (
    EatAction,
    MoveAction,
    PerceivedAgent,
    PerceivedPlant,
    Perception,
)
from core.decision.rule_based import BrainParams, RuleBasedBrain
from core.genome import Genome
from core.phenotype import express
from core.rng import Rng
from core.vector import Vector
import config


_PARAMS = config.BRAIN_PARAMS


def _genome(**overrides) -> Genome:
    base = {
        "size": 0.5, "speed": 0.5, "vision_budget": 0.5, "vision_focus": 0.5,
        "diet": 0.5, "repro_threshold": 0.5, "metabolism": 0.5,
        "offspring_investment": 0.5,
        "aggression": 0.5, "fear": 0.5, "exploration": 0.5,
    }
    base.update(overrides)
    return Genome.from_values(config.GENOME_SCHEMA, base)


def _brain(aggression=0.5, fear=0.5, exploration=0.0, params=_PARAMS) -> RuleBasedBrain:
    g = _genome(aggression=aggression, fear=fear, exploration=exploration)
    return RuleBasedBrain.express(g, params)


def _phenotype(**overrides):
    return express(_genome(**overrides), config.PHENOTYPE_PARAMS)


def _perception(*, agents=(), plants=(), phenotype=None, energy=100.0, heading=None):
    return Perception(
        nearby_agents=tuple(agents),
        nearby_plants=tuple(plants),
        own_energy=energy,
        own_phenotype=phenotype if phenotype is not None else _phenotype(),
        own_heading=heading if heading is not None else Vector(1.0, 0.0),
    )


# --- expression (方案甲: personality baked in) -------------------------------

def test_express_reads_personality_genes_from_genome():
    g = _genome(aggression=0.8, fear=0.2, exploration=0.6)
    brain = RuleBasedBrain.express(g, _PARAMS)
    assert brain.aggression == pytest.approx(0.8)
    assert brain.fear == pytest.approx(0.2)
    assert brain.exploration == pytest.approx(0.6)


# --- rung 1: flee ------------------------------------------------------------

def test_flees_from_near_larger_carnivore():
    me = _phenotype(size=0.5)
    threat = PerceivedAgent(id=7, relative_position=Vector(10.0, 0.0), size=0.9, diet=1.0, body_radius=9.0)
    brain = _brain(fear=0.5)  # flee distance = 0.5 * 100 = 50 > 10
    action = brain.decide(_perception(agents=[threat], phenotype=me), Rng(1))
    assert isinstance(action, MoveAction)
    assert action.speed_fraction == 1.0
    # Direction is directly away from the threat.
    assert action.direction == Vector(-10.0, 0.0)


def test_does_not_flee_when_threat_beyond_fear_distance():
    me = _phenotype(size=0.5)
    threat = PerceivedAgent(id=7, relative_position=Vector(80.0, 0.0), size=0.9, diet=1.0, body_radius=9.0)
    brain = _brain(fear=0.1)  # flee distance = 10 < 80 -> no flee
    action = brain.decide(_perception(agents=[threat], phenotype=me), Rng(1))
    # No threat reaction -> falls through; with no food it wanders/rests, never a flee away-vector.
    assert not (isinstance(action, MoveAction) and action.direction == Vector(-80.0, 0.0))


def test_non_carnivore_neighbour_is_not_a_threat():
    me = _phenotype(size=0.5)
    big_grazer = PerceivedAgent(id=7, relative_position=Vector(5.0, 0.0), size=0.9, diet=0.0, body_radius=9.0)
    brain = _brain(fear=1.0)
    action = brain.decide(_perception(agents=[big_grazer], phenotype=me), Rng(1))
    assert action.direction != Vector(-5.0, 0.0)


def test_similar_size_carnivore_is_not_a_threat():
    me = _phenotype(size=0.8)
    peer = PerceivedAgent(id=7, relative_position=Vector(5.0, 0.0), size=0.85, diet=1.0, body_radius=8.5)
    # 0.85 is not > 0.8 * 1.2 = 0.96, so no predation threat.
    brain = _brain(fear=1.0)
    action = brain.decide(_perception(agents=[peer], phenotype=me), Rng(1))
    assert action.direction != Vector(-5.0, 0.0)


# --- rung 2: eat -------------------------------------------------------------

def test_herbivore_eats_plant_in_contact():
    me = _phenotype(size=0.5, diet=0.0)  # plant_eat_prob = 1.0 -> deterministic
    # my radius = 5; plant radius = 3; reach = 8; place within reach.
    plant = PerceivedPlant(id=42, relative_position=Vector(4.0, 0.0), body_radius=3.0)
    action = _brain().decide(_perception(plants=[plant], phenotype=me), Rng(1))
    assert action == EatAction(target_id=42)


def test_carnivore_eats_prey_in_contact_with_size_advantage():
    me = _phenotype(size=0.9, diet=1.0)  # prey_eat_prob = 1.0
    # 0.9 > 0.5 * 1.2 = 0.6 -> size advantage. reach = 9 + 5 = 14.
    prey = PerceivedAgent(id=5, relative_position=Vector(6.0, 0.0), size=0.5, diet=0.0, body_radius=5.0)
    action = _brain().decide(_perception(agents=[prey], phenotype=me), Rng(1))
    assert action == EatAction(target_id=5)


def test_carnivore_does_not_eat_plant_in_contact():
    me = _phenotype(size=0.5, diet=1.0)  # plant_eat_prob = 0.0 -> never bites a plant
    plant = PerceivedPlant(id=42, relative_position=Vector(2.0, 0.0), body_radius=3.0)
    action = _brain(aggression=0.5).decide(_perception(plants=[plant], phenotype=me), Rng(1))
    assert not isinstance(action, EatAction)


def test_no_eat_without_size_advantage_over_prey():
    me = _phenotype(size=0.5, diet=1.0)
    # contact but no size advantage (0.5 is not > 0.5 * 1.2) -> cannot prey.
    other = PerceivedAgent(id=5, relative_position=Vector(3.0, 0.0), size=0.5, diet=0.0, body_radius=5.0)
    action = _brain().decide(_perception(agents=[other], phenotype=me), Rng(1))
    assert not isinstance(action, EatAction)


def test_eat_probability_is_drawn_from_rng():
    # An omnivore (diet=0.5) eats a plant with prob plant_eat_prob = (1-0.5)^herb_exp.
    # Derive the expectation from the phenotype (not a magic number) so this test
    # stays valid as the niche-curve exponent is tuned; just assert the observed
    # rate tracks it and is clearly neither never nor always.
    me = _phenotype(size=0.5, diet=0.5)
    expected = me.plant_eat_prob * 400
    plant = PerceivedPlant(id=42, relative_position=Vector(1.0, 0.0), body_radius=3.0)
    eats = sum(
        1
        for s in range(400)
        if isinstance(_brain().decide(_perception(plants=[plant], phenotype=me), Rng(s)), EatAction)
    )
    assert 0 < eats < 400              # stochastic: not deterministic either way
    assert 0.7 * expected < eats < 1.3 * expected  # rate tracks the configured prob


# --- rung 3: hunt / forage ---------------------------------------------------

def test_sprints_toward_distant_prey():
    me = _phenotype(size=0.9, diet=1.0)
    # Out of contact (reach 14, placed at 50), in sight.
    prey = PerceivedAgent(id=5, relative_position=Vector(50.0, 0.0), size=0.5, diet=0.0, body_radius=5.0)
    action = _brain(aggression=1.0).decide(_perception(agents=[prey], phenotype=me), Rng(1))
    assert isinstance(action, MoveAction)
    assert action.direction == Vector(50.0, 0.0)
    assert action.speed_fraction == 1.0


def test_cruises_toward_distant_plant():
    me = _phenotype(size=0.5, diet=0.0)
    plant = PerceivedPlant(id=42, relative_position=Vector(50.0, 0.0), body_radius=3.0)
    action = _brain().decide(_perception(plants=[plant], phenotype=me), Rng(1))
    assert isinstance(action, MoveAction)
    assert action.direction == Vector(50.0, 0.0)
    assert action.speed_fraction == pytest.approx(_PARAMS.cruise_speed_fraction)


def test_prefers_prey_when_prey_value_higher():
    me = _phenotype(size=0.9, diet=1.0)  # prey_gain high, plant_gain ~0
    prey = PerceivedAgent(id=5, relative_position=Vector(50.0, 0.0), size=0.4, diet=0.0, body_radius=4.0)
    plant = PerceivedPlant(id=42, relative_position=Vector(10.0, 0.0), body_radius=3.0)
    action = _brain(aggression=1.0).decide(_perception(agents=[prey], plants=[plant], phenotype=me), Rng(1))
    assert action.direction == Vector(50.0, 0.0)  # heads for prey, not the nearer plant
    assert action.speed_fraction == 1.0


def test_pacifist_carnivore_does_not_hunt():
    me = _phenotype(size=0.9, diet=1.0)
    prey = PerceivedAgent(id=5, relative_position=Vector(50.0, 0.0), size=0.4, diet=0.0, body_radius=4.0)
    # aggression 0 -> prey_value 0 -> no hunt; with no plants, wanders/rests.
    action = _brain(aggression=0.0, exploration=0.0).decide(_perception(agents=[prey], phenotype=me), Rng(1))
    assert action.direction != Vector(50.0, 0.0)


# --- rung 4: wander / rest ---------------------------------------------------

def test_rests_when_nothing_around_and_no_exploration():
    action = _brain(exploration=0.0).decide(_perception(heading=Vector(0.0, 1.0)), Rng(1))
    assert isinstance(action, MoveAction)
    assert action.speed_fraction == 0.0


def test_wanders_when_exploration_certain():
    action = _brain(exploration=1.0).decide(_perception(), Rng(1))
    assert isinstance(action, MoveAction)
    assert action.speed_fraction == pytest.approx(_PARAMS.cruise_speed_fraction)
    assert action.direction.length() == pytest.approx(1.0)  # unit random direction


def test_wander_direction_matches_world_dimension():
    # 3D heading -> 3D random direction, with no perceived entities to borrow dim from.
    action = _brain(exploration=1.0).decide(_perception(heading=Vector(0.0, 0.0, 1.0)), Rng(2))
    assert action.direction.dim == 3


# --- purity / determinism ----------------------------------------------------

def test_decide_is_deterministic_for_same_seed():
    me = _phenotype(size=0.5, diet=0.5)
    plant = PerceivedPlant(id=42, relative_position=Vector(1.0, 0.0), body_radius=3.0)
    a1 = _brain().decide(_perception(plants=[plant], phenotype=me), Rng(99))
    a2 = _brain().decide(_perception(plants=[plant], phenotype=me), Rng(99))
    assert a1 == a2
