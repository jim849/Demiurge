"""Tests for core.plant -- the discrete, immutable food entity."""

import pytest

from core.plant import Plant, PlantParams
from core.vector import Vector


def test_construct_sets_fields():
    p = Plant(id=3, position=Vector(10.0, 20.0), body_radius=3.0, energy=30.0)
    assert p.id == 3
    assert p.position == Vector(10.0, 20.0)
    assert p.body_radius == 3.0
    assert p.energy == 30.0


def test_is_immutable():
    p = Plant(id=1, position=Vector(0.0, 0.0), body_radius=3.0, energy=30.0)
    with pytest.raises(Exception):
        p.energy = 99.0  # type: ignore[misc]


def test_rejects_non_positive_radius():
    with pytest.raises(ValueError):
        Plant(id=1, position=Vector(0.0, 0.0), body_radius=0.0, energy=30.0)


def test_rejects_non_positive_energy():
    with pytest.raises(ValueError):
        Plant(id=1, position=Vector(0.0, 0.0), body_radius=3.0, energy=0.0)


# --- PlantParams -------------------------------------------------------------

def test_plant_params_sets_fields():
    pp = PlantParams(energy=30.0, body_radius=3.0, regen_per_tick=4, max_count=600)
    assert pp.energy == 30.0
    assert pp.body_radius == 3.0
    assert pp.regen_per_tick == 4
    assert pp.max_count == 600


@pytest.mark.parametrize("kwargs", [
    dict(energy=0.0, body_radius=3.0, regen_per_tick=4, max_count=600),
    dict(energy=30.0, body_radius=0.0, regen_per_tick=4, max_count=600),
    dict(energy=30.0, body_radius=3.0, regen_per_tick=-1, max_count=600),
    dict(energy=30.0, body_radius=3.0, regen_per_tick=4, max_count=-1),
])
def test_plant_params_validates(kwargs):
    with pytest.raises(ValueError):
        PlantParams(**kwargs)
