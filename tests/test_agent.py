"""Tests for core.agent.

The Agent is a lean state container: these tests pin down its state-integrity
methods (energy floor, re-expression after a gene edit, death flag) and confirm
it stays free of decision/reproduction policy.
"""

import pytest

from core.agent import Agent
from core.genome import Genome
from core.phenotype import express
from core.vector import Vector
import config


def _genome(**overrides) -> Genome:
    base = {
        "size": 0.5, "speed": 0.5, "vision_budget": 0.5, "vision_focus": 0.5,
        "diet": 0.5, "repro_threshold": 0.5, "metabolism": 0.5,
        "offspring_investment": 0.5,
        "aggression": 0.5, "fear": 0.5, "exploration": 0.5,
    }
    base.update(overrides)
    return Genome.from_values(config.GENOME_SCHEMA, base)


def _agent(**kwargs) -> Agent:
    g = kwargs.pop("genome", None) or _genome()
    p = express(g, config.PHENOTYPE_PARAMS)
    pos = kwargs.pop("position", Vector(10.0, 20.0))
    return Agent(kwargs.pop("agent_id", 1), g, p, pos, **kwargs)


# --- construction & defaults -------------------------------------------------

def test_construct_sets_state():
    a = _agent(agent_id=7, energy=12.5, generation=3)
    assert a.id == 7
    assert a.energy == 12.5
    assert a.generation == 3
    assert a.age == 0
    assert a.alive is True


def test_heading_defaults_to_zero_of_matching_dim():
    a = _agent(position=Vector(1.0, 2.0, 3.0))
    assert a.heading == Vector.zero(3)


def test_explicit_heading_kept():
    a = _agent(heading=Vector(1.0, 0.0))
    assert a.heading == Vector(1.0, 0.0)


def test_negative_energy_rejected():
    with pytest.raises(ValueError):
        _agent(energy=-1.0)


def test_negative_generation_rejected():
    with pytest.raises(ValueError):
        _agent(generation=-1)


# --- energy integrity --------------------------------------------------------

def test_add_energy_increases():
    a = _agent(energy=5.0)
    a.add_energy(3.0)
    assert a.energy == 8.0


def test_spend_energy_decreases():
    a = _agent(energy=5.0)
    a.spend_energy(2.0)
    assert a.energy == 3.0


def test_spend_energy_clamps_at_zero():
    a = _agent(energy=1.0)
    a.spend_energy(5.0)
    assert a.energy == 0.0


def test_add_energy_rejects_negative():
    a = _agent(energy=5.0)
    with pytest.raises(ValueError):
        a.add_energy(-1.0)


def test_spend_energy_rejects_negative():
    a = _agent(energy=5.0)
    with pytest.raises(ValueError):
        a.spend_energy(-1.0)


# --- age & death -------------------------------------------------------------

def test_advance_age():
    a = _agent()
    a.advance_age()
    a.advance_age()
    assert a.age == 2


def test_mark_dead():
    a = _agent()
    a.mark_dead()
    assert a.alive is False


# --- re-expression after a gene edit -----------------------------------------

def test_re_express_rebuilds_phenotype_after_gene_change():
    g = _genome(size=0.2)
    a = _agent(genome=g)
    before = a.phenotype
    a.genome.set("size", 0.9)
    a.re_express(config.PHENOTYPE_PARAMS)
    assert a.phenotype is not before
    # bigger body -> higher move cost (the trade-off encoded in phenotype)
    assert a.phenotype.move_cost(3.0) > before.move_cost(3.0)


def test_phenotype_remains_immutable_value():
    a = _agent()
    with pytest.raises(Exception):
        a.phenotype.max_speed = 99.0  # type: ignore[misc]


# --- lean container: no policy methods ---------------------------------------

def test_agent_has_no_decision_or_reproduction_policy():
    a = _agent()
    for forbidden in ("decide", "move", "eat", "reproduce", "hunt"):
        assert not hasattr(a, forbidden), f"Agent should not own policy method {forbidden!r}"
