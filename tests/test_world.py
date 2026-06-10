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
from core.plant import PlantParams
from core.recording import Recorder
from core.rng import Rng
from core.vector import Vector
from core.world import AgentSnapshot, PredationParams, World, WorldSnapshot
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


# --- plants: storage, scatter, snapshot --------------------------------------

def test_new_world_has_no_plants():
    assert _world().plants == {}


def test_spawn_plant_registers_and_wraps():
    w = _world(size=Vector(100.0, 100.0))
    p = w.spawn_plant(Vector(150.0, -10.0), energy=30.0, body_radius=3.0)
    assert w.plants[p.id] is p
    assert p.position == Vector(50.0, 90.0)  # wrapped into the torus
    assert p.energy == 30.0
    assert p.body_radius == 3.0


def test_plants_and_agents_share_id_space():
    w = _world()
    a = w.spawn_agent(_random_genome(), Vector(10.0, 10.0))
    p = w.spawn_plant(Vector(20.0, 20.0), energy=30.0, body_radius=3.0)
    assert a.id == 0 and p.id == 1  # one counter across both tables


def test_scatter_plants_count_and_bounds():
    w = _world(size=Vector(100.0, 60.0))
    w.scatter_plants(40, energy=30.0, body_radius=3.0)
    assert len(w.plants) == 40
    for p in w.plants.values():
        assert 0.0 <= p.position.x < 100.0
        assert 0.0 <= p.position.y < 60.0


def test_scatter_plants_is_reproducible_for_same_seed():
    def positions():
        w = _world()
        w.scatter_plants(8, energy=30.0, body_radius=3.0)
        return [p.position for p in w.plants.values()]
    assert positions() == positions()


def test_scatter_plants_independent_of_agent_population():
    # Plant layout must not shift when the agent population changes (separate
    # named sub-stream). Compare plant positions with and without agents present.
    w1 = _world()
    w1.scatter_plants(8, energy=30.0, body_radius=3.0)
    w2 = _world()
    w2.populate(20, initial_energy=10.0)
    w2.scatter_plants(8, energy=30.0, body_radius=3.0)
    assert [p.position for p in w1.plants.values()] == \
           [p.position for p in w2.plants.values()]


def test_scatter_plants_rejects_negative_count():
    with pytest.raises(ValueError):
        _world().scatter_plants(-1, energy=30.0, body_radius=3.0)


def test_snapshot_includes_plants():
    w = _world()
    w.scatter_plants(3, energy=30.0, body_radius=3.0)
    snap = w.snapshot()
    assert len(snap.plants) == 3
    p = next(iter(w.plants.values()))
    s = snap.plants[0]
    assert s.id == p.id
    assert s.position == p.position
    assert s.body_radius == p.body_radius


# --- plants: perception -------------------------------------------------------

def test_perceives_plant_ahead_within_range():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)  # panoramic
    w = _world(size=_BIG)
    obs = w.spawn_agent(obs_g, _ORIGIN, heading=Vector(1.0, 0.0))
    r = obs.phenotype.perception_range * 0.5
    plant = w.spawn_plant(_ORIGIN + Vector(r, 0.0), energy=30.0, body_radius=3.0)
    p = w.perceive(obs)
    assert len(p.nearby_plants) == 1
    assert p.nearby_plants[0].id == plant.id
    assert p.nearby_plants[0].relative_position == Vector(r, 0.0)
    assert p.nearby_plants[0].body_radius == 3.0


def test_does_not_perceive_plant_beyond_range():
    obs_g = _genome(vision_focus=0.0, vision_budget=1.0)
    w = _world(size=_BIG)
    obs = w.spawn_agent(obs_g, _ORIGIN, heading=Vector(1.0, 0.0))
    beyond = obs.phenotype.perception_range * 2.0
    w.spawn_plant(_ORIGIN + Vector(beyond, 0.0), energy=30.0, body_radius=3.0)
    assert w.perceive(obs).nearby_plants == ()


def test_narrow_cone_excludes_plant_behind():
    obs_g = _genome(vision_focus=1.0, vision_budget=1.0)  # narrow cone
    w = _world(size=_BIG)
    obs = w.spawn_agent(obs_g, _ORIGIN, heading=Vector(1.0, 0.0))
    r = obs.phenotype.perception_range * 0.5
    behind = w.spawn_plant(_ORIGIN + Vector(-r, 0.0), energy=30.0, body_radius=3.0)
    assert w.perceive(obs).nearby_plants == ()
    # but a plant straight ahead is seen
    w.plants.pop(behind.id)
    w.spawn_plant(_ORIGIN + Vector(r, 0.0), energy=30.0, body_radius=3.0)
    assert len(w.perceive(obs).nearby_plants) == 1


# --- herbivory: eating resolution --------------------------------------------

class _PlantEaterBrain(DecisionMaker):
    """Always tries to eat the first perceived plant; rests otherwise."""

    def decide(self, perception, rng):
        if perception.nearby_plants:
            return EatAction(target_id=perception.nearby_plants[0].id)
        return MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.0)


def _eater_world(size=Vector(1000.0, 1000.0)) -> World:
    return World(
        size,
        Rng(config.DEFAULT_SEED),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=lambda g: _PlantEaterBrain(),
    )


# herbivore + panoramic so it both sees and digests a plant fully
_HERB = dict(diet=0.0, vision_focus=0.0, vision_budget=1.0)


def test_herbivore_eats_adjacent_plant_and_gains_energy():
    w = _eater_world()
    a = w.spawn_agent(_genome(**_HERB), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    plant = w.spawn_plant(_ORIGIN + Vector(4.0, 0.0), energy=30.0, body_radius=3.0)  # reach=5+3=8
    gain = a.phenotype.plant_gain * plant.energy
    rest = a.phenotype.resting_cost
    w.tick()
    assert plant.id not in w.plants                       # consumed whole
    assert a.energy == pytest.approx(100.0 + gain - rest)  # gained, then paid metabolism


def test_eat_requires_contact_world_is_authoritative():
    w = _eater_world()
    a = w.spawn_agent(_genome(**_HERB), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    # visible (within range) but well beyond reach -> brain still emits EatAction
    plant = w.spawn_plant(_ORIGIN + Vector(20.0, 0.0), energy=30.0, body_radius=3.0)
    rest = a.phenotype.resting_cost
    w.tick()
    assert plant.id in w.plants                       # not eaten: out of contact
    assert a.energy == pytest.approx(100.0 - rest)    # only metabolism, no gain


def test_only_one_agent_wins_a_contested_plant():
    w = _eater_world()
    # one plant flanked by two herbivores, both in contact (reach 8)
    a0 = w.spawn_agent(_genome(**_HERB), _ORIGIN + Vector(-4.0, 0.0), heading=Vector(1.0, 0.0), energy=100.0)
    a1 = w.spawn_agent(_genome(**_HERB), _ORIGIN + Vector(4.0, 0.0), heading=Vector(-1.0, 0.0), energy=100.0)
    plant = w.spawn_plant(_ORIGIN, energy=30.0, body_radius=3.0)
    gain = a0.phenotype.plant_gain * plant.energy
    rest = a0.phenotype.resting_cost
    w.tick()
    assert plant.id not in w.plants
    energies = sorted([a0.energy, a1.energy])
    assert energies[0] == pytest.approx(100.0 - rest)         # loser: metabolism only
    assert energies[1] == pytest.approx(100.0 + gain - rest)  # winner: ate it


def test_contested_plant_winner_is_reproducible():
    def run():
        w = _eater_world()
        w.spawn_agent(_genome(**_HERB), _ORIGIN + Vector(-4.0, 0.0), heading=Vector(1.0, 0.0), energy=100.0)
        w.spawn_agent(_genome(**_HERB), _ORIGIN + Vector(4.0, 0.0), heading=Vector(-1.0, 0.0), energy=100.0)
        w.spawn_plant(_ORIGIN, energy=30.0, body_radius=3.0)
        w.tick()
        return [a.energy for a in w.agents.values()]
    assert run() == run()


def test_omnivore_gains_less_than_herbivore_from_same_plant():
    def delta(diet):
        w = _eater_world()
        a = w.spawn_agent(_genome(diet=diet, vision_focus=0.0, vision_budget=1.0),
                          _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
        w.spawn_plant(_ORIGIN + Vector(4.0, 0.0), energy=30.0, body_radius=3.0)
        rest = a.phenotype.resting_cost
        w.tick()
        return a.energy - (100.0 - rest)  # pure food gain, metabolism removed
    assert delta(0.5) < delta(0.0)
    assert delta(0.5) > 0.0


# --- PredationParams ----------------------------------------------------------

def test_predation_params_sets_fields():
    pp = PredationParams(size_ratio=1.2, body_value_coeff=0.3)
    assert pp.size_ratio == 1.2
    assert pp.body_value_coeff == 0.3


@pytest.mark.parametrize("kwargs", [
    dict(size_ratio=0.0, body_value_coeff=0.3),    # ratio must be positive
    dict(size_ratio=-1.0, body_value_coeff=0.3),
    dict(size_ratio=1.2, body_value_coeff=-0.1),   # coeff may be 0 but not negative
])
def test_predation_params_validates(kwargs):
    with pytest.raises(ValueError):
        PredationParams(**kwargs)


# --- predation: carnivores eating prey ---------------------------------------

class _PreyEaterBrain(DecisionMaker):
    """Targets the smallest perceived agent (its best prey); rests if none seen.

    Picking the smallest body keeps the test brain from wasting its bite on a
    same-size rival it could never kill -- it goes for the most plausible prey.
    """

    def decide(self, perception, rng):
        if perception.nearby_agents:
            target = min(perception.nearby_agents, key=lambda a: a.body_radius)
            return EatAction(target_id=target.id)
        return MoveAction(direction=Vector(1.0, 0.0), speed_fraction=0.0)


def _hunter_world(size=_BIG, *, predation=True) -> World:
    return World(
        size,
        Rng(config.DEFAULT_SEED),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=lambda g: _PreyEaterBrain(),
        predation_params=config.PREDATION_PARAMS if predation else None,
    )


# a big carnivore that both sees (panoramic) and digests (diet=1) its prey
_HUNT = dict(size=0.8, diet=1.0, vision_focus=0.0, vision_budget=1.0)


def test_carnivore_eats_adjacent_prey_and_gains_energy():
    w = _hunter_world()
    hunter = w.spawn_agent(_genome(**_HUNT), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    prey = w.spawn_agent(_genome(size=0.2, diet=0.0), _ORIGIN + Vector(4.0, 0.0), energy=80.0)
    coeff = config.PREDATION_PARAMS.body_value_coeff
    meal = 80.0 + coeff * prey.phenotype.body_radius ** 2   # reserves + structural biomass
    gain = hunter.phenotype.prey_gain * meal
    rest = hunter.phenotype.resting_cost
    w.tick()
    assert prey.id not in w.agents                          # killed and reaped
    assert hunter.energy == pytest.approx(100.0 + gain - rest)


def test_predation_requires_size_advantage():
    w = _hunter_world()
    # hunter only marginally bigger: 0.5 is not > 1.2 * 0.45, so no kill
    hunter = w.spawn_agent(_genome(size=0.5, diet=1.0, vision_focus=0.0, vision_budget=1.0),
                           _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    prey = w.spawn_agent(_genome(size=0.45, diet=0.0), _ORIGIN + Vector(4.0, 0.0), energy=80.0)
    rest = hunter.phenotype.resting_cost
    w.tick()
    assert prey.id in w.agents                              # survives: edge too small
    assert hunter.energy == pytest.approx(100.0 - rest)


def test_predation_requires_contact_world_is_authoritative():
    w = _hunter_world()
    hunter = w.spawn_agent(_genome(**_HUNT), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    # visible (within range) but well beyond reach (8 + 2 = 10) -> brain still bites
    prey = w.spawn_agent(_genome(size=0.2, diet=0.0), _ORIGIN + Vector(20.0, 0.0), energy=80.0)
    rest = hunter.phenotype.resting_cost
    w.tick()
    assert prey.id in w.agents                              # not eaten: out of contact
    assert hunter.energy == pytest.approx(100.0 - rest)


def test_predation_disabled_without_params():
    # With no predation economy, prey EatActions are ignored (prey survives).
    w = _hunter_world(predation=False)
    hunter = w.spawn_agent(_genome(**_HUNT), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    prey = w.spawn_agent(_genome(size=0.2, diet=0.0), _ORIGIN + Vector(4.0, 0.0), energy=80.0)
    rest = hunter.phenotype.resting_cost
    w.tick()
    assert prey.id in w.agents
    assert hunter.energy == pytest.approx(100.0 - rest)


def test_meal_value_includes_prey_body_not_just_energy():
    # "A camel starved to death still outweighs a horse": a nearly-empty but large
    # prey still yields a substantial meal -- the structural term dominates.
    w = _hunter_world()
    hunter = w.spawn_agent(_genome(size=1.0, diet=1.0, vision_focus=0.0, vision_budget=1.0),
                           _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    prey = w.spawn_agent(_genome(size=0.6, diet=0.0), _ORIGIN + Vector(3.0, 0.0), energy=0.5)
    coeff = config.PREDATION_PARAMS.body_value_coeff
    structural = coeff * prey.phenotype.body_radius ** 2
    gain = hunter.phenotype.prey_gain * (0.5 + structural)
    rest = hunter.phenotype.resting_cost
    w.tick()
    assert prey.id not in w.agents
    assert hunter.energy == pytest.approx(100.0 + gain - rest)
    assert structural > 0.5                                 # structure beats the empty reserves


def test_contested_prey_has_one_winner_reproducible():
    def run():
        w = _hunter_world()
        # two big hunters flanking one small prey; both see and reach it
        w.spawn_agent(_genome(**_HUNT), _ORIGIN + Vector(-4.0, 0.0), heading=Vector(1.0, 0.0), energy=100.0)
        w.spawn_agent(_genome(**_HUNT), _ORIGIN + Vector(4.0, 0.0), heading=Vector(-1.0, 0.0), energy=100.0)
        w.spawn_agent(_genome(size=0.2, diet=0.0), _ORIGIN, energy=80.0)
        w.tick()
        return sorted(a.energy for a in w.agents.values())
    first = run()
    assert first == run()                                   # reproducible winner
    assert len(first) == 2                                  # prey killed and reaped
    assert first[0] != pytest.approx(first[1])              # one fed, one went hungry


def test_prey_cannot_flee_within_the_same_tick():
    # Eat-before-move: a prey that sprints away is still caught, because contact is
    # judged at tick-start positions.
    class _Fleer(DecisionMaker):
        def decide(self, perception, rng):
            return MoveAction(direction=Vector(1.0, 0.0), speed_fraction=1.0)

    def factory(genome):
        return _PreyEaterBrain() if genome.get("diet") >= 0.5 else _Fleer()

    w = World(_BIG, Rng(config.DEFAULT_SEED), schema=config.GENOME_SCHEMA,
              phenotype_params=config.PHENOTYPE_PARAMS, brain_factory=factory,
              predation_params=config.PREDATION_PARAMS)
    hunter = w.spawn_agent(_genome(**_HUNT), _ORIGIN, heading=Vector(1.0, 0.0), energy=100.0)
    prey = w.spawn_agent(_genome(size=0.2, diet=0.0), _ORIGIN + Vector(4.0, 0.0), energy=80.0)
    w.tick()
    assert prey.id not in w.agents                          # caught despite fleeing


# --- plant regrowth -----------------------------------------------------------

def _plant_world(plant_params, size=Vector(200.0, 200.0)) -> World:
    return World(
        size,
        Rng(config.DEFAULT_SEED),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=_brain_factory,
        plant_params=plant_params,
    )


def test_no_regrowth_without_plant_params():
    w = _world(size=Vector(200.0, 200.0))  # no plant_params
    w.scatter_plants(5, energy=30.0, body_radius=3.0)
    w.tick()  # no agents -> nothing eaten; no plant economy -> nothing regrows
    assert len(w.plants) == 5


def test_regrowth_adds_fixed_rate_then_caps():
    pp = PlantParams(energy=30.0, body_radius=3.0, regen_per_tick=4, max_count=10)
    w = _plant_world(pp)  # no agents: plants only regrow, never eaten
    w.tick()
    assert len(w.plants) == 4
    w.tick()
    assert len(w.plants) == 8
    w.tick()
    assert len(w.plants) == 10  # room was 2 -> only 2 added
    w.tick()
    assert len(w.plants) == 10  # capped


def test_regrowth_is_reproducible():
    pp = PlantParams(energy=30.0, body_radius=3.0, regen_per_tick=4, max_count=100)
    def run():
        w = _plant_world(pp)
        for _ in range(3):
            w.tick()
        return [p.position for p in w.plants.values()]
    assert run() == run()


def test_regrowth_replenishes_food_supply_over_time():
    pp = PlantParams(energy=30.0, body_radius=3.0, regen_per_tick=5, max_count=50)
    w = _plant_world(pp)
    assert len(w.plants) == 0
    for _ in range(5):
        w.tick()
    assert len(w.plants) == 25  # 5 per tick, well under cap -> never permanently empty
