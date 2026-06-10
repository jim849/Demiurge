"""Tests for core.world -- sub-step 1: container, deterministic setup, snapshot.

These pin down: the World owns a monotonic id counter (iron law 7); toroidal
wrap on every axis; brain injection via a factory (iron law 5, no concrete brain
imported into World); deterministic population from a single seed (iron laws 7,
8); and that snapshots are immutable pure data (iron laws 1, 2). The two-phase
tick is tested later.
"""

import pytest

from core.decision.base import DecisionMaker, EatAction, MoveAction, Perception
from core.decision.rule_based import RuleBasedBrain
from core.genome import Genome
from core.recording import Recorder
from core.rng import Rng
from core.vector import Vector
from core.world import AgentSnapshot, World, WorldSnapshot
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


# --- initial heading ----------------------------------------------------------

def test_populate_assigns_unit_headings():
    w = _world()
    w.populate(5, initial_energy=10.0)
    for a in w.agents.values():
        assert a.heading.length() == pytest.approx(1.0)


def test_headings_are_reproducible_for_same_seed():
    def headings():
        w = _world()
        w.populate(4, initial_energy=10.0)
        return [a.heading for a in w.agents.values()]
    assert headings() == headings()


# --- toroidal delta -----------------------------------------------------------

def test_toroidal_delta_takes_short_way_around():
    w = _world(size=Vector(100.0, 100.0))
    # 90 -> 5 is +15 going forward across the seam, not -85 going back.
    assert w.toroidal_delta(Vector(90.0, 50.0), Vector(5.0, 50.0)) == Vector(15.0, 0.0)
    assert w.toroidal_delta(Vector(5.0, 50.0), Vector(90.0, 50.0)) == Vector(-15.0, 0.0)


# --- perception: range + field of view ---------------------------------------

# A big world so wrap doesn't interfere with the geometry under test.
_BIG = Vector(10_000.0, 10_000.0)
_ORIGIN = Vector(5_000.0, 5_000.0)


def _two_agent_world(observer_genome, observer_heading, target_offset, target_genome=None):
    """Spawn an observer at the centre facing `observer_heading`, plus one target
    at `_ORIGIN + target_offset`. Returns (world, observer, target)."""
    w = _world(size=_BIG)
    obs = w.spawn_agent(observer_genome, _ORIGIN, heading=observer_heading)
    tgt = w.spawn_agent(target_genome or _genome(), _ORIGIN + target_offset)
    return w, obs, tgt


def test_perceive_returns_perception_with_self_state():
    w, obs, _ = _two_agent_world(_genome(), Vector(1.0, 0.0), Vector(1.0, 0.0))
    p = w.perceive(obs)
    assert isinstance(p, Perception)
    assert p.own_phenotype is obs.phenotype
    assert p.own_energy == obs.energy
    assert p.own_heading == obs.heading
    assert p.nearby_plants == ()


def test_perceives_target_directly_ahead_within_range():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)  # panoramic
    w, obs, tgt = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(1.0, 0.0))
    ahead = obs.phenotype.perception_range * 0.5
    # move target to a known spot inside range, straight ahead
    w.agents[tgt.id].position = _ORIGIN + Vector(ahead, 0.0)
    p = w.perceive(obs)
    assert len(p.nearby_agents) == 1
    assert p.nearby_agents[0].id == tgt.id
    assert p.nearby_agents[0].relative_position == Vector(ahead, 0.0)


def test_does_not_perceive_beyond_range():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)
    w, obs, tgt = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(1.0, 0.0))
    beyond = obs.phenotype.perception_range * 2.0
    w.agents[tgt.id].position = _ORIGIN + Vector(beyond, 0.0)
    assert w.perceive(obs).nearby_agents == ()


def test_narrow_cone_excludes_target_to_the_side_and_behind():
    obs_g = _genome(vision_focus=1.0, vision_budget=1.0)  # telephoto, narrow cone
    w, obs, _ = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(1.0, 0.0))
    r = obs.phenotype.perception_range * 0.5
    # directly ahead -> seen
    w.agents[1].position = _ORIGIN + Vector(r, 0.0)
    assert len(w.perceive(obs).nearby_agents) == 1
    # 90 degrees to the side -> outside the narrow cone
    w.agents[1].position = _ORIGIN + Vector(0.0, r)
    assert w.perceive(obs).nearby_agents == ()
    # directly behind -> outside
    w.agents[1].position = _ORIGIN + Vector(-r, 0.0)
    assert w.perceive(obs).nearby_agents == ()


def test_panoramic_sees_in_every_direction():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)  # half-angle = pi
    w, obs, _ = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(1.0, 0.0))
    r = obs.phenotype.perception_range * 0.5
    for offset in (Vector(r, 0.0), Vector(0.0, r), Vector(-r, 0.0), Vector(0.0, -r)):
        w.agents[1].position = _ORIGIN + offset
        assert len(w.perceive(obs).nearby_agents) == 1


def test_perceive_excludes_self():
    w = _world(size=_BIG)
    obs = w.spawn_agent(_genome(vision_focus=0.0, vision_budget=1.0), _ORIGIN,
                        heading=Vector(1.0, 0.0))
    assert w.perceive(obs).nearby_agents == ()


def test_perceive_excludes_dead_agents():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)
    w, obs, tgt = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(5.0, 0.0))
    assert len(w.perceive(obs).nearby_agents) == 1
    w.agents[tgt.id].mark_dead()
    assert w.perceive(obs).nearby_agents == ()


def test_perceived_target_carries_body_attributes():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)
    tgt_g = _genome(size=0.8, diet=0.9)
    w, obs, tgt = _two_agent_world(obs_g, Vector(1.0, 0.0), Vector(5.0, 0.0), target_genome=tgt_g)
    pa = w.perceive(obs).nearby_agents[0]
    assert pa.size == pytest.approx(0.8)
    assert pa.diet == pytest.approx(0.9)
    assert pa.body_radius == pytest.approx(tgt.phenotype.body_radius)


def test_perception_uses_toroidal_distance_across_the_seam():
    w = _world(size=Vector(100.0, 100.0))
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)
    # observer near the right edge, target just across the seam on the left edge
    obs = w.spawn_agent(obs_g, Vector(98.0, 50.0), heading=Vector(1.0, 0.0))
    assert obs.phenotype.perception_range > 4.0  # sanity: range covers the gap
    w.spawn_agent(_genome(), Vector(2.0, 50.0))  # 4 units away across the wrap
    p = w.perceive(obs)
    assert len(p.nearby_agents) == 1
    assert p.nearby_agents[0].relative_position == Vector(4.0, 0.0)


# --- the two-phase tick -------------------------------------------------------

class _FixedBrain(DecisionMaker):
    """A brain that always returns the same action -- for resolve-phase tests."""

    def __init__(self, action):
        self._action = action

    def decide(self, perception, rng):
        return self._action


def _fixed_world(action, *, size=Vector(1000.0, 1000.0)) -> World:
    return World(
        size,
        Rng(config.DEFAULT_SEED),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=lambda g: _FixedBrain(action),
    )


class _ListRecorder(Recorder):
    def __init__(self):
        self.ticks = []

    def record_tick(self, snapshot):
        self.ticks.append(snapshot.tick)


def test_tick_advances_count():
    w = _world()
    w.populate(3, initial_energy=1000.0)
    w.tick()
    w.tick()
    assert w.tick_count == 2


def test_resting_agent_ages_and_pays_resting_cost():
    w = _fixed_world(MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.0))
    a = w.spawn_agent(_genome(), Vector(50.0, 50.0), heading=Vector(1.0, 0.0), energy=1000.0)
    before_pos, before_energy = a.position, a.energy
    w.tick()
    assert a.age == 1
    assert a.position == before_pos  # rest -> no displacement
    assert a.energy == pytest.approx(before_energy - a.phenotype.resting_cost)


def test_moving_agent_advances_and_pays_move_cost():
    w = _fixed_world(MoveAction(direction=Vector(1.0, 0.0), speed_fraction=1.0))
    a = w.spawn_agent(_genome(), Vector(50.0, 50.0), heading=Vector(1.0, 0.0), energy=1000.0)
    speed = a.phenotype.max_speed
    expected_cost = a.phenotype.move_cost(speed) + a.phenotype.resting_cost
    before_energy = a.energy
    w.tick()
    assert a.position == Vector(50.0 + speed, 50.0)
    assert a.heading == Vector(1.0, 0.0)
    assert a.energy == pytest.approx(before_energy - expected_cost)


def test_movement_wraps_around_torus():
    w = _fixed_world(MoveAction(direction=Vector(1.0, 0.0), speed_fraction=1.0),
                     size=Vector(100.0, 100.0))
    a = w.spawn_agent(_genome(), Vector(98.0, 50.0), heading=Vector(1.0, 0.0), energy=1000.0)
    speed = a.phenotype.max_speed
    w.tick()
    assert a.position.x == pytest.approx((98.0 + speed) % 100.0)
    assert a.position.y == pytest.approx(50.0)


def test_eat_action_is_noop_but_still_pays_resting_cost():
    w = _fixed_world(EatAction(target_id=999))
    a = w.spawn_agent(_genome(), Vector(50.0, 50.0), heading=Vector(1.0, 0.0), energy=1000.0)
    before_pos, before_energy = a.position, a.energy
    w.tick()
    assert a.position == before_pos
    assert a.age == 1
    assert a.energy == pytest.approx(before_energy - a.phenotype.resting_cost)


def test_agent_dies_and_is_reaped_when_energy_exhausted():
    w = _fixed_world(MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.0))
    a = w.spawn_agent(_genome(), Vector(50.0, 50.0), heading=Vector(1.0, 0.0), energy=0.01)
    assert a.phenotype.resting_cost > 0.01  # sanity: this tick is fatal
    w.tick()
    assert a.id not in w.agents  # reaped
    assert w.tick_count == 1


def test_tick_is_deterministic_for_same_seed():
    def run():
        w = _world()
        w.populate(6, initial_energy=200.0)
        for _ in range(10):
            w.tick()
        return w.snapshot()
    assert run() == run()


def test_recorder_receives_every_tick():
    rec = _ListRecorder()
    w = World(Vector(1000.0, 1000.0), Rng(config.DEFAULT_SEED),
              schema=config.GENOME_SCHEMA, phenotype_params=config.PHENOTYPE_PARAMS,
              brain_factory=_brain_factory, recorder=rec)
    w.populate(3, initial_energy=1000.0)
    w.tick()
    w.tick()
    w.tick()
    assert rec.ticks == [1, 2, 3]
