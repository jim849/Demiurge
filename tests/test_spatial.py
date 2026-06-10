"""Tests for core.spatial.UniformGrid -- the perception accelerator.

The grid's one contract is: `query(center, radius)` returns a *superset* of the
items within `radius` (no false negatives), so swapping brute force for the grid
never changes what an agent perceives. The key tests check that contract against
a brute-force toroidal search on random layouts, plus the toroidal seam and the
degenerate single-cell world.
"""

import pytest

from core.rng import Rng
from core.spatial import UniformGrid
from core.vector import Vector


def _toroidal_distance_sq(a: Vector, b: Vector, size: Vector) -> float:
    """Minimum-image squared distance on the torus (the brute-force reference)."""
    total = 0.0
    for s, t, extent in zip(a, b, size):
        d = (t - s) % extent
        if d > extent / 2.0:
            d -= extent
        total += d * d
    return total


def _brute_within(items, center, radius, size):
    """Ids whose toroidal distance to center is <= radius (the ground truth)."""
    r_sq = radius * radius
    return {
        item
        for pos, item in items
        if _toroidal_distance_sq(pos, center, size) <= r_sq
    }


# --- construction / validation ----------------------------------------------

def test_cell_size_must_be_positive():
    with pytest.raises(ValueError):
        UniformGrid(Vector(100.0, 100.0), 0.0)


def test_every_extent_must_be_positive():
    with pytest.raises(ValueError):
        UniformGrid(Vector(100.0, -1.0), 10.0)


# --- basic query behaviour --------------------------------------------------

def test_empty_grid_yields_nothing():
    grid: UniformGrid[int] = UniformGrid(Vector(100.0, 100.0), 10.0)
    assert list(grid.query(Vector(50.0, 50.0), 30.0)) == []


def test_negative_radius_yields_nothing():
    grid: UniformGrid[int] = UniformGrid(Vector(100.0, 100.0), 10.0)
    grid.insert(Vector(50.0, 50.0), 1)
    assert list(grid.query(Vector(50.0, 50.0), -1.0)) == []


def test_finds_item_at_center():
    grid: UniformGrid[int] = UniformGrid(Vector(100.0, 100.0), 10.0)
    grid.insert(Vector(50.0, 50.0), 7)
    assert 7 in set(grid.query(Vector(50.0, 50.0), 1.0))


def test_rebuild_clears_previous_contents():
    grid: UniformGrid[int] = UniformGrid(Vector(100.0, 100.0), 10.0)
    grid.insert(Vector(10.0, 10.0), 1)
    grid.rebuild([(Vector(80.0, 80.0), 2)])
    found = set(grid.query(Vector(80.0, 80.0), 5.0))
    assert found == {2}  # the old item 1 is gone


# --- the toroidal seam ------------------------------------------------------

def test_finds_neighbour_across_the_wrap_seam():
    size = Vector(100.0, 100.0)
    grid: UniformGrid[int] = UniformGrid(size, 10.0)
    grid.insert(Vector(98.0, 50.0), 1)  # near the right edge
    # A query centred near the left edge: straight-line distance is 93, but the
    # toroidal distance is 7 -- the grid must fold across the seam to find it.
    found = set(grid.query(Vector(5.0, 50.0), 10.0))
    assert found == {1}


def test_finds_neighbour_across_a_corner_seam():
    size = Vector(100.0, 100.0)
    grid: UniformGrid[int] = UniformGrid(size, 10.0)
    grid.insert(Vector(98.0, 97.0), 1)  # tucked in a far corner
    found = set(grid.query(Vector(2.0, 3.0), 10.0))  # opposite corner, dist ~5.7
    assert found == {1}


# --- degenerate worlds ------------------------------------------------------

def test_world_smaller_than_a_cell_collapses_to_one_cell():
    # cell_size larger than the world -> a single bucket holding everything.
    size = Vector(30.0, 30.0)
    grid: UniformGrid[int] = UniformGrid(size, 100.0)
    grid.rebuild([(Vector(1.0, 1.0), 1), (Vector(29.0, 29.0), 2)])
    # Even a tiny-radius query returns the whole (single) cell; the caller's exact
    # test then filters. Superset contract still holds.
    assert set(grid.query(Vector(1.0, 1.0), 0.1)) == {1, 2}


def test_huge_radius_returns_everything():
    size = Vector(100.0, 100.0)
    items = [(Vector(float(x), float(y)), x * 100 + y) for x in range(0, 100, 13) for y in range(0, 100, 17)]
    grid: UniformGrid[int] = UniformGrid(size, 10.0)
    grid.rebuild(items)
    found = set(grid.query(Vector(50.0, 50.0), 1000.0))
    assert found == {item for _pos, item in items}


# --- the core contract: no false negatives vs brute force -------------------

@pytest.mark.parametrize("cell_size", [10.0, 33.0, 100.0, 250.0])
def test_query_is_a_superset_of_brute_force(cell_size):
    """On random layouts, every item within radius (toroidal) must be returned."""
    size = Vector(200.0, 200.0)
    rng = Rng(2026)
    items = []
    for i in range(300):
        pos = Vector(rng.uniform(0.0, 200.0), rng.uniform(0.0, 200.0))
        items.append((pos, i))
    grid: UniformGrid[int] = UniformGrid(size, cell_size)
    grid.rebuild(items)

    for _ in range(50):
        center = Vector(rng.uniform(0.0, 200.0), rng.uniform(0.0, 200.0))
        radius = rng.uniform(1.0, 90.0)
        truth = _brute_within(items, center, radius, size)
        found = set(grid.query(center, radius))
        # Superset: nothing within the radius may be missed (found may hold extras).
        assert truth <= found


def test_superset_holds_in_three_dimensions():
    """Dimension-agnostic: the same contract must hold for a 3D box."""
    size = Vector(120.0, 120.0, 120.0)
    rng = Rng(7)
    items = []
    for i in range(200):
        pos = Vector(
            rng.uniform(0.0, 120.0),
            rng.uniform(0.0, 120.0),
            rng.uniform(0.0, 120.0),
        )
        items.append((pos, i))
    grid: UniformGrid[int] = UniformGrid(size, 40.0)
    grid.rebuild(items)

    for _ in range(30):
        center = Vector(
            rng.uniform(0.0, 120.0),
            rng.uniform(0.0, 120.0),
            rng.uniform(0.0, 120.0),
        )
        radius = rng.uniform(1.0, 50.0)
        truth = _brute_within(items, center, radius, size)
        assert truth <= set(grid.query(center, radius))
