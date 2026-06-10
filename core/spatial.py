"""Uniform spatial grid: fast neighbour queries on a torus.

Perception is the simulation's hot path: naively, every agent tests its toroidal
distance to every other entity, which is O(N^2) per tick. This grid buckets
entities by position so a range query only scans the handful of cells that could
possibly contain a neighbour, turning the per-tick cost into roughly O(N).

Design decisions:
- **Acceleration only, never authority.** `query(center, radius)` returns a
  *superset* of the items within `radius`: every item within the radius is
  guaranteed to be returned (no false negatives), plus some just outside it. The
  caller still applies the exact distance (and field-of-view) test. The grid
  changes *which* items you test, never *which* ones pass -- so results are
  identical to brute force.
- **Toroidal.** Cell indices wrap with modulo, and a query whose box runs off an
  edge (negative or past the extent) folds onto the cells on the opposite edge.
  This is what makes a neighbour across the seam count as close.
- **Dimension-agnostic.** Cell indices are integer tuples; the scanned region is
  the Cartesian product of per-axis index ranges, so the same code serves a 2D
  plane now and a 3D box later (matches the rest of the core).
- **Rebuilt, not updated.** Entities move every tick; rebuilding from scratch is
  O(N) and trivially correct, so there is no incremental-update bookkeeping.
- **Cone pruning is deliberately NOT done.** A narrow field of view only sweeps a
  thin wedge of the bounding box, so a future optimisation could skip cells the
  cone never enters -- but that helps only narrow-focus, long-range agents (rare),
  is geometrically fiddly, and would break dimension-agnosticism. The bounding-box
  scan already removes the O(N^2) blow-up; cone pruning is a documented future
  knob, not a v1 concern.

The grid stores nothing tunable itself; `cell_size` is a pure performance knob
passed in from config (iron law 10) -- it changes speed, never results.
"""

from __future__ import annotations

from itertools import product
from typing import Generic, Iterable, Iterator, TypeVar

from core.vector import Vector

T = TypeVar("T")


class UniformGrid(Generic[T]):
    """A toroidal, dimension-agnostic uniform grid bucketing items by position."""

    __slots__ = ("_size", "_cell", "_ncells", "_cells")

    def __init__(self, size: Vector, cell_size: float) -> None:
        if cell_size <= 0:
            raise ValueError("cell_size must be positive")
        if any(extent <= 0 for extent in size):
            raise ValueError("every grid extent must be positive")
        self._size = size
        # An integer number of cells per axis so they tile the torus exactly (clean
        # modulo wrap). floor keeps each effective cell at least `cell_size` wide; a
        # world smaller than one cell collapses to a single cell on that axis.
        self._ncells: tuple[int, ...] = tuple(
            max(1, int(extent // cell_size)) for extent in size
        )
        self._cell: tuple[float, ...] = tuple(
            extent / n for extent, n in zip(size, self._ncells)
        )
        self._cells: dict[tuple[int, ...], list[tuple[Vector, T]]] = {}

    # --- build ---------------------------------------------------------------

    def _cell_index(self, position: Vector) -> tuple[int, ...]:
        """The (wrapped) integer cell coordinates a position falls in."""
        return tuple(
            int(comp // c) % n
            for comp, c, n in zip(position, self._cell, self._ncells)
        )

    def insert(self, position: Vector, item: T) -> None:
        """Bucket one item at `position`."""
        self._cells.setdefault(self._cell_index(position), []).append((position, item))

    def rebuild(self, items: Iterable[tuple[Vector, T]]) -> None:
        """Discard all buckets and re-bucket `items` (the per-tick refresh)."""
        self._cells.clear()
        for position, item in items:
            self.insert(position, item)

    # --- query ---------------------------------------------------------------

    def query(self, center: Vector, radius: float) -> Iterator[T]:
        """Yield every item within `radius` of `center`, plus some just outside.

        A superset query (no false negatives): it returns all items whose toroidal
        distance to `center` is <= `radius`. The caller applies the exact test. The
        scanned region is the set of cells covering the axis-aligned box
        [center - radius, center + radius], folded onto the torus by modulo.
        """
        if radius < 0:
            return
        axis_ranges: list[Iterable[int]] = []
        for comp, c, n in zip(center, self._cell, self._ncells):
            lo = int((comp - radius) // c)
            hi = int((comp + radius) // c)
            if hi - lo + 1 >= n:
                axis_ranges.append(range(n))  # box covers the whole axis
            else:
                # `span < n` consecutive integers stay distinct after `% n`, so the
                # Cartesian product visits each cell at most once (no dedup needed).
                axis_ranges.append([k % n for k in range(lo, hi + 1)])

        cells = self._cells
        for index in product(*axis_ranges):
            bucket = cells.get(index)
            if bucket is not None:
                for _position, item in bucket:
                    yield item

    def __repr__(self) -> str:
        return f"UniformGrid(ncells={self._ncells}, items={sum(len(b) for b in self._cells.values())})"
