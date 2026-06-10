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
from render.projection import Camera, diet_color


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
