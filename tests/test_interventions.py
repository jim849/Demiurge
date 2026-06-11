"""Tests for demiurge.interventions -- the creator's three capabilities.

These pin down: read returns a full flat gene view; edit is range-validated and
*re-expresses* the agent (so phenotype AND brain reflect the change, not just the
stored gene); create requires a complete gene dict and places the agent into the
world via the World's own spawn path (id assigned, position wrapped, phenotype +
brain expressed). Pure logic, headless (iron laws 1, 9).
"""

import pytest

from core.decision.rule_based import RuleBasedBrain
from core.genome import Genome
from core.rng import Rng
from core.vector import Vector
from core.world import World
from demiurge.interventions import Demiurge
import config


def _brain_factory(genome):
    return RuleBasedBrain.express(genome, config.BRAIN_PARAMS)


def _world(*, size=Vector(100.0, 100.0), seed=config.DEFAULT_SEED) -> World:
    return World(
        size,
        Rng(seed),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=_brain_factory,
    )


def _genes(**overrides) -> dict[str, float]:
    base = {
        "size": 0.5, "speed": 0.5, "vision_budget": 0.5, "vision_focus": 0.5,
        "diet": 0.5, "repro_threshold": 0.5, "metabolism": 0.5,
        "offspring_investment": 0.5,
        "aggression": 0.5, "fear": 0.5, "exploration": 0.5,
    }
    base.update(overrides)
    return base


def _demiurge(world: World) -> Demiurge:
    return Demiurge(world, config.GENOME_SCHEMA)


# --- capability 1: read -------------------------------------------------------

def test_read_genes_returns_full_flat_view():
    world = _world()
    agent = world.spawn_agent(Genome.from_values(config.GENOME_SCHEMA, _genes(diet=0.7)), Vector(10.0, 10.0))
    genes = _demiurge(world).read_genes(agent.id)
    assert genes == _genes(diet=0.7)


def test_read_unknown_agent_raises():
    world = _world()
    with pytest.raises(KeyError):
        _demiurge(world).read_genes(999)


# --- capability 2: edit -------------------------------------------------------

def test_edit_gene_changes_stored_value():
    world = _world()
    agent = world.spawn_agent(Genome.from_values(config.GENOME_SCHEMA, _genes()), Vector(0.0, 0.0))
    _demiurge(world).edit_gene(agent.id, "diet", 0.9)
    assert agent.genome.get("diet") == pytest.approx(0.9)


def test_edit_gene_re_expresses_phenotype():
    # diet flows into the phenotype's plant/prey gains; editing it must rebuild
    # the cached phenotype, not just the stored gene.
    world = _world()
    agent = world.spawn_agent(Genome.from_values(config.GENOME_SCHEMA, _genes(diet=0.0)), Vector(0.0, 0.0))
    before = agent.phenotype.prey_eat_prob
    _demiurge(world).edit_gene(agent.id, "diet", 1.0)
    after = agent.phenotype.prey_eat_prob
    assert after > before  # carnivory rose -> phenotype was re-expressed


def test_edit_brain_gene_re_expresses_brain():
    # aggression is baked into the brain instance at expression (方案甲); editing
    # it must rebuild the brain, or the change is silently ignored.
    world = _world()
    agent = world.spawn_agent(Genome.from_values(config.GENOME_SCHEMA, _genes(aggression=0.2)), Vector(0.0, 0.0))
    _demiurge(world).edit_gene(agent.id, "aggression", 0.85)
    assert isinstance(agent.decision_maker, RuleBasedBrain)
    assert agent.decision_maker.aggression == pytest.approx(0.85)


def test_edit_out_of_range_raises_and_leaves_value_untouched():
    world = _world()
    agent = world.spawn_agent(Genome.from_values(config.GENOME_SCHEMA, _genes(diet=0.3)), Vector(0.0, 0.0))
    with pytest.raises(ValueError):
        _demiurge(world).edit_gene(agent.id, "diet", 1.5)  # diet range is [0, 1]
    assert agent.genome.get("diet") == pytest.approx(0.3)  # unchanged


def test_edit_unknown_agent_raises():
    world = _world()
    with pytest.raises(KeyError):
        _demiurge(world).edit_gene(123, "diet", 0.5)


# --- capability 3: create -----------------------------------------------------

def test_create_agent_places_into_world():
    world = _world()
    agent = _demiurge(world).create_agent(_genes(diet=0.9), Vector(20.0, 30.0), energy=80.0)
    assert world.agents[agent.id] is agent
    assert agent.energy == pytest.approx(80.0)
    assert agent.genome.get("diet") == pytest.approx(0.9)
    assert isinstance(agent.decision_maker, RuleBasedBrain)  # brain expressed


def test_create_agent_wraps_position_into_torus():
    world = _world(size=Vector(100.0, 100.0))
    agent = _demiurge(world).create_agent(_genes(), Vector(120.0, -10.0))
    assert agent.position == Vector(20.0, 90.0)


def test_create_agent_requires_complete_gene_dict():
    world = _world()
    partial = _genes()
    del partial["diet"]
    with pytest.raises(ValueError):
        _demiurge(world).create_agent(partial, Vector(0.0, 0.0))


def test_create_agent_rejects_extra_genes():
    world = _world()
    extra = _genes()
    extra["nonsense"] = 0.5
    with pytest.raises(ValueError):
        _demiurge(world).create_agent(extra, Vector(0.0, 0.0))


def test_created_agents_get_distinct_ids():
    world = _world()
    d = _demiurge(world)
    a = d.create_agent(_genes(), Vector(0.0, 0.0))
    b = d.create_agent(_genes(), Vector(0.0, 0.0))
    assert a.id != b.id
