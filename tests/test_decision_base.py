"""Tests for core.decision.base — the brain interface contract.

This module holds no decision logic (that's rule_based.py later); these tests pin
down the value objects (immutability, validation), the id-based targeting, and
that DecisionMaker is an abstract, RNG-injected pure-function interface.
"""

import pytest

from core.decision.base import (
    Action,
    DecisionMaker,
    EatAction,
    MoveAction,
    PerceivedAgent,
    PerceivedPlant,
    Perception,
)
from core.genome import Genome
from core.phenotype import express
from core.rng import Rng
from core.vector import Vector
import config


def _phenotype():
    g = Genome.from_values(config.GENOME_SCHEMA, {
        "size": 0.5, "speed": 0.5, "vision_budget": 0.5, "vision_focus": 0.5,
        "diet": 0.5, "repro_threshold": 0.5, "metabolism": 0.5,
        "offspring_investment": 0.5,
        "aggression": 0.5, "fear": 0.5, "exploration": 0.5,
    })
    return express(g, config.PHENOTYPE_PARAMS)


# --- perception value objects ------------------------------------------------

def test_perception_holds_relative_entities_and_self_state():
    ph = _phenotype()
    p = Perception(
        nearby_agents=(PerceivedAgent(id=2, relative_position=Vector(3.0, 4.0), size=0.7, diet=0.9, body_radius=7.0),),
        nearby_plants=(PerceivedPlant(id=9, relative_position=Vector(-1.0, 0.0), body_radius=3.0),),
        own_energy=42.0,
        own_phenotype=ph,
        own_heading=Vector(0.0, 1.0),
    )
    assert p.own_heading == Vector(0.0, 1.0)
    assert p.nearby_agents[0].id == 2
    assert p.nearby_agents[0].relative_position == Vector(3.0, 4.0)
    assert p.nearby_agents[0].size == 0.7
    assert p.nearby_agents[0].diet == 0.9
    assert p.nearby_agents[0].body_radius == 7.0
    assert p.nearby_plants[0].id == 9
    assert p.nearby_plants[0].body_radius == 3.0
    assert p.own_energy == 42.0
    assert p.own_phenotype is ph


def test_perceived_entities_are_immutable():
    a = PerceivedAgent(id=1, relative_position=Vector(0.0, 0.0), size=0.5, diet=0.5, body_radius=5.0)
    with pytest.raises(Exception):
        a.size = 0.9  # type: ignore[misc]


def test_perception_is_immutable():
    p = Perception(nearby_agents=(), nearby_plants=(), own_energy=1.0, own_phenotype=_phenotype(), own_heading=Vector(1.0, 0.0))
    with pytest.raises(Exception):
        p.own_energy = 2.0  # type: ignore[misc]


# --- actions -----------------------------------------------------------------

def test_move_action_holds_direction_and_fraction():
    m = MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.5)
    assert m.direction == Vector(1.0, 0.0)
    assert m.speed_fraction == 0.5
    assert isinstance(m, Action)


def test_move_action_rest_is_zero_fraction():
    rest = MoveAction(direction=Vector(0.0, 0.0), speed_fraction=0.0)
    assert rest.speed_fraction == 0.0


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_move_action_rejects_out_of_range_fraction(bad):
    with pytest.raises(ValueError):
        MoveAction(direction=Vector(1.0, 0.0), speed_fraction=bad)


def test_eat_action_references_target_by_id():
    e = EatAction(target_id=11)
    assert e.target_id == 11
    assert isinstance(e, Action)


def test_actions_are_immutable():
    m = MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.5)
    with pytest.raises(Exception):
        m.speed_fraction = 0.1  # type: ignore[misc]


# --- the interface -----------------------------------------------------------

def test_decisionmaker_is_abstract():
    with pytest.raises(TypeError):
        DecisionMaker()  # type: ignore[abstract]


def test_concrete_decisionmaker_implements_decide():
    class FixedBrain(DecisionMaker):
        def decide(self, perception, rng):
            return MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.0)

    brain = FixedBrain()
    p = Perception(nearby_agents=(), nearby_plants=(), own_energy=1.0, own_phenotype=_phenotype(), own_heading=Vector(1.0, 0.0))
    action = brain.decide(p, Rng(1))
    assert isinstance(action, MoveAction)


def test_decide_receives_injected_rng():
    seen = {}

    class RngBrain(DecisionMaker):
        def decide(self, perception, rng):
            seen["rng"] = rng
            return EatAction(target_id=rng.randint(0, 5))

    rng = Rng(7)
    p = Perception(nearby_agents=(), nearby_plants=(), own_energy=1.0, own_phenotype=_phenotype(), own_heading=Vector(1.0, 0.0))
    RngBrain().decide(p, rng)
    assert seen["rng"] is rng
