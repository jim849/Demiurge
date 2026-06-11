"""Tests for the render layer.

Two halves:
- the PURE projection/colour helpers (render.projection), tested headless with no
  pygame at all;
- a HEADLESS SMOKE of the pygame loop (render.view) under SDL's dummy video
  driver -- it never opens a real window, just proves the event/draw loop runs
  and tears down cleanly.
"""

import os

import pytest

from core.vector import Vector
from core.world import AgentSnapshot, WorldSnapshot
from render.projection import Camera, diet_color, pick_agent


def _ag(id_: int, x: float, y: float, body_radius: float) -> AgentSnapshot:
    return AgentSnapshot(
        id=id_, position=Vector(x, y), heading=Vector(1.0, 0.0),
        body_radius=body_radius, energy=10.0, size=0.5, diet=0.5,
        alive=True, generation=0,
    )


def _snap(*agents: AgentSnapshot) -> WorldSnapshot:
    return WorldSnapshot(tick=0, size=Vector(1000.0, 1000.0), agents=tuple(agents), plants=())


# --- pure: diet colour -------------------------------------------------------

def test_diet_color_endpoints_are_green_and_red():
    herb = diet_color(0.0)
    carn = diet_color(1.0)
    assert herb[1] > herb[0] and herb[1] > herb[2]   # greenest channel dominates
    assert carn[0] > carn[1] and carn[0] > carn[2]   # reddest channel dominates


def test_diet_color_clamps_out_of_range():
    assert diet_color(-5.0) == diet_color(0.0)
    assert diet_color(5.0) == diet_color(1.0)


def test_diet_color_midpoint_is_between_endpoints():
    herb, mid, carn = diet_color(0.0), diet_color(0.5), diet_color(1.0)
    for lo, m, hi in zip(herb, mid, carn):
        assert min(lo, hi) <= m <= max(lo, hi)


# --- pure: camera mapping ----------------------------------------------------

def test_camera_rejects_non_2d_world():
    with pytest.raises(ValueError):
        Camera(Vector(100.0, 100.0, 100.0), 800)
    with pytest.raises(ValueError):
        Camera(Vector(100.0), 800)


def test_camera_rejects_nonpositive_viewport():
    with pytest.raises(ValueError):
        Camera(Vector(100.0, 100.0), 0)


def test_scale_fits_larger_extent_into_viewport():
    cam = Camera(Vector(1000.0, 500.0), 800)
    assert cam.scale == 800 / 1000.0  # the larger extent (1000) fills the viewport


def test_to_screen_scales_world_to_pixels():
    cam = Camera(Vector(1000.0, 1000.0), 800)  # scale 0.8
    assert cam.to_screen(Vector(100.0, 200.0)) == (80, 160)
    assert cam.to_screen(Vector(0.0, 0.0)) == (0, 0)


def test_to_world_is_inverse_of_to_screen():
    cam = Camera(Vector(1000.0, 1000.0), 800)
    world = cam.to_world(80, 160)
    assert world.x == pytest.approx(100.0)
    assert world.y == pytest.approx(200.0)


def test_radius_px_honours_minimum():
    cam = Camera(Vector(1000.0, 1000.0), 800)  # scale 0.8
    assert cam.radius_px(10.0) == 8
    assert cam.radius_px(0.1, minimum=2) == 2  # tiny body floored to stay visible


# --- pure: click hit test ----------------------------------------------------

def test_pick_agent_hits_body():
    cam = Camera(Vector(1000.0, 1000.0), 800)  # scale 0.8
    snap = _snap(_ag(7, 100.0, 100.0, body_radius=20.0))
    assert pick_agent(snap, Vector(105.0, 100.0), cam) == 7  # inside the body
    assert pick_agent(snap, Vector(130.0, 100.0), cam) is None  # outside -> empty


def test_pick_agent_empty_space_returns_none():
    cam = Camera(Vector(1000.0, 1000.0), 800)
    assert pick_agent(_snap(), Vector(50.0, 50.0), cam) is None


def test_pick_agent_nearest_center_wins_when_overlapping():
    cam = Camera(Vector(1000.0, 1000.0), 800)
    snap = _snap(
        _ag(1, 100.0, 100.0, body_radius=50.0),
        _ag(2, 140.0, 100.0, body_radius=50.0),
    )
    # the click at x=115 is inside both discs but nearer agent 1's centre
    assert pick_agent(snap, Vector(115.0, 100.0), cam) == 1
    assert pick_agent(snap, Vector(132.0, 100.0), cam) == 2


def test_pick_agent_floors_tiny_body_to_min_radius():
    cam = Camera(Vector(1000.0, 1000.0), 800)  # scale 0.8 -> 2px == 2.5 world units
    snap = _snap(_ag(3, 100.0, 100.0, body_radius=0.1))  # sub-pixel body
    # within the floored clickable disc (2.5 world units) though far outside the body
    assert pick_agent(snap, Vector(102.0, 100.0), cam) == 3
    assert pick_agent(snap, Vector(104.0, 100.0), cam) is None  # beyond the floor


# --- headless smoke of the pygame loop --------------------------------------

def _tiny_world():
    """A small but real world (a few agents + plants) for the loop smoke."""
    import config
    from core.decision.rule_based import RuleBasedBrain
    from core.rng import Rng
    from core.world import World

    world = World(
        Vector(200.0, 200.0),
        Rng(1),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=lambda g: RuleBasedBrain.express(g, config.BRAIN_PARAMS),
        plant_params=config.PLANT_PARAMS,
    )
    world.populate(8, initial_energy=config.INITIAL_AGENT_ENERGY)
    world.scatter_plants(12, energy=config.PLANT_PARAMS.energy, body_radius=config.PLANT_PARAMS.body_radius)
    return world


def test_view_loop_runs_and_tears_down_headless():
    # Force SDL to use non-visual drivers BEFORE pygame initialises any subsystem.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from render.view import run

    run(_tiny_world(), viewport_px=200, panel_px=80, max_frames=3)
    assert not pygame.get_init()  # run() must clean up pygame on exit


def test_view_click_selects_agent_and_draws_inspect_panel():
    # A real click over an agent's pixel must flow through to world.select(), and
    # the resulting inspect panel + highlight ring must render without error.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    from render.projection import Camera
    from render.view import run

    world = _tiny_world()
    target = min(world.agents)  # an id we know exists
    camera = Camera(world.size, 200)  # viewport matches the run() call below
    px, py = camera.to_screen(world.agents[target].position)

    pygame.init()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(px, py)))
    # The click is hit-tested against the pre-tick snapshot, so the target is under
    # the cursor when selected; a couple of ticks afterwards won't unselect it (the
    # agent is well-fed and survives), letting the inspect panel render at least once.
    run(world, viewport_px=200, panel_px=240, ticks_per_frame=1, max_frames=2)

    assert world.selected_id == target
    assert not pygame.get_init()
