"""Tests for core.world -- sub-step 1: container, deterministic setup, snapshot.

These pin down: the World owns a monotonic id counter (iron law 7); toroidal
wrap on every axis; brain injection via a factory (iron law 5, no concrete brain
imported into World); deterministic population from a single seed (iron laws 7,
8); and that snapshots are immutable pure data (iron laws 1, 2). The two-phase
tick is tested later.
"""

import pytest

from core.decision.base import DecisionMaker
from core.decision.rule_based import RuleBasedBrain
from core.genome import Genome
from core.rng import Rng
from core.vector import Vector
from core.world import AgentSnapshot, World, WorldSnapshot
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


def _random_genome(seed=1) -> Genome:
    return Genome.random(config.GENOME_SCHEMA, Rng(seed))


# --- construction -------------------------------------------------------------

def test_new_world_is_empty_at_tick_zero():
    w = _world()
    assert w.tick_count == 0
    assert w.agents == {}
    assert w.size == Vector(100.0, 100.0)


def test_rejects_non_positive_extent():
    with pytest.raises(ValueError):
        World(Vector(100.0, 0.0), Rng(1), schema=config.GENOME_SCHEMA,
              phenotype_params=config.PHENOTYPE_PARAMS, brain_factory=_brain_factory)


# --- toroidal wrap ------------------------------------------------------------

def test_wrap_overflow_and_underflow():
    w = _world(size=Vector(100.0, 50.0))
    assert w.wrap(Vector(110.0, 60.0)) == Vector(10.0, 10.0)
    assert w.wrap(Vector(-10.0, -5.0)) == Vector(90.0, 45.0)


def test_wrap_inside_is_unchanged():
    w = _world(size=Vector(100.0, 100.0))
    assert w.wrap(Vector(42.0, 7.0)) == Vector(42.0, 7.0)


def test_wrap_dimension_mismatch_raises():
    w = _world(size=Vector(100.0, 100.0))
    with pytest.raises(ValueError):
        w.wrap(Vector(1.0, 2.0, 3.0))


# --- birth: id allocation & brain injection ----------------------------------

def test_spawn_assigns_monotonic_ids_and_registers():
    w = _world()
    g = _random_genome()
    a0 = w.spawn_agent(g, Vector(10.0, 10.0))
    a1 = w.spawn_agent(g.copy(), Vector(20.0, 20.0))
    assert a0.id == 0 and a1.id == 1
    assert w.agents[0] is a0 and w.agents[1] is a1


def test_spawned_agent_has_phenotype_and_brain():
    w = _world()
    a = w.spawn_agent(_random_genome(), Vector(10.0, 10.0))
    assert a.phenotype is not None
    assert isinstance(a.decision_maker, DecisionMaker)


def test_spawn_wraps_position_into_torus():
    w = _world(size=Vector(100.0, 100.0))
    a = w.spawn_agent(_random_genome(), Vector(150.0, -10.0))
    assert a.position == Vector(50.0, 90.0)


# --- deterministic population -------------------------------------------------

def test_populate_count_and_state():
    w = _world()
    w.populate(8, initial_energy=25.0)
    assert len(w.agents) == 8
    for a in w.agents.values():
        assert a.energy == 25.0
        assert a.generation == 0
        assert a.alive is True


def test_populate_is_reproducible_for_same_seed():
    def build():
        w = _world()
        w.populate(6, initial_energy=10.0)
        return w.snapshot()
    a = build()
    b = build()
    assert [(s.id, s.position, s.size, s.diet) for s in a.agents] == \
           [(s.id, s.position, s.size, s.diet) for s in b.agents]


def test_populate_differs_for_different_seed():
    def build(seed):
        w = _world(seed=seed)
        w.populate(6, initial_energy=10.0)
        return w.snapshot()
    assert [s.position for s in build(1).agents] != [s.position for s in build(2).agents]


def test_populate_positions_inside_bounds():
    w = _world(size=Vector(100.0, 60.0))
    w.populate(50, initial_energy=10.0)
    for a in w.agents.values():
        assert 0.0 <= a.position.x < 100.0
        assert 0.0 <= a.position.y < 60.0


def test_populate_rejects_negative_count():
    w = _world()
    with pytest.raises(ValueError):
        w.populate(-1, initial_energy=10.0)


# --- snapshot: pure, immutable data ------------------------------------------

def test_snapshot_mirrors_world_state():
    w = _world()
    w.populate(3, initial_energy=10.0)
    snap = w.snapshot()
    assert isinstance(snap, WorldSnapshot)
    assert snap.tick == 0
    assert snap.size == w.size
    assert len(snap.agents) == 3
    assert [s.id for s in snap.agents] == [0, 1, 2]  # ordered by id


def test_snapshot_fields_match_agents():
    w = _world()
    w.populate(1, initial_energy=10.0)
    a = w.agents[0]
    s = w.snapshot().agents[0]
    assert isinstance(s, AgentSnapshot)
    assert s.id == a.id
    assert s.position == a.position
    assert s.heading == a.heading
    assert s.body_radius == a.phenotype.body_radius
    assert s.energy == a.energy
    assert s.size == a.genome.get("size")
    assert s.diet == a.genome.get("diet")
    assert s.alive == a.alive


def test_snapshot_is_immutable():
    w = _world()
    w.populate(1, initial_energy=10.0)
    snap = w.snapshot()
    with pytest.raises(Exception):
        snap.tick = 5  # type: ignore[misc]
    with pytest.raises(Exception):
        snap.agents[0].energy = 999.0  # type: ignore[misc]
