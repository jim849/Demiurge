"""Dimension-agnostic, immutable vector for positions and directions.

Design decisions (see PLAN.md, Milestone 1):
- **Dimension-agnostic** (iron law 3): a Vector holds N components, so the same
  type works for 2D now and 3D later without changing this class.
- **Immutable**: operations return new Vectors instead of mutating in place.
  Safer to reason about and friendlier to reproducibility (iron law 7).
- **Pure Python**: a single vector is cheap in plain Python. Batch/vectorized
  work (e.g. the render snapshot of all agents at once) belongs to a NumPy
  layer, not here.

This module is pure math. World rules such as toroidal (wrap-around) boundaries
live in world.py, NOT here, so that Vector stays a generic geometric primitive.
"""

from __future__ import annotations

import math
from typing import Iterable, Iterator


class Vector:
    """An immutable N-dimensional vector backed by a tuple of floats."""

    __slots__ = ("_components",)

    def __init__(self, *components: float) -> None:
        if not components:
            raise ValueError("Vector requires at least one component")
        # Store as a tuple of floats: immutable and order-stable.
        object.__setattr__(self, "_components", tuple(float(c) for c in components))

    # --- construction helpers -------------------------------------------------

    @classmethod
    def from_iterable(cls, components: Iterable[float]) -> "Vector":
        """Build a Vector from any iterable of numbers."""
        return cls(*components)

    @classmethod
    def zero(cls, dim: int) -> "Vector":
        """Return the zero vector of the given dimension."""
        if dim < 1:
            raise ValueError("dimension must be >= 1")
        return cls(*([0.0] * dim))

    # --- immutability guard ---------------------------------------------------

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Vector is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Vector is immutable")

    # --- access ---------------------------------------------------------------

    @property
    def components(self) -> tuple[float, ...]:
        return self._components

    @property
    def dim(self) -> int:
        return len(self._components)

    @property
    def x(self) -> float:
        return self._components[0]

    @property
    def y(self) -> float:
        if self.dim < 2:
            raise AttributeError("vector has no y component")
        return self._components[1]

    @property
    def z(self) -> float:
        if self.dim < 3:
            raise AttributeError("vector has no z component")
        return self._components[2]

    def __getitem__(self, index: int) -> float:
        return self._components[index]

    def __iter__(self) -> Iterator[float]:
        return iter(self._components)

    def __len__(self) -> int:
        return len(self._components)

    # --- internal -------------------------------------------------------------

    def _check_same_dim(self, other: "Vector") -> None:
        if self.dim != other.dim:
            raise ValueError(
                f"dimension mismatch: {self.dim} vs {other.dim}"
            )

    # --- arithmetic (all return new Vectors) ----------------------------------

    def __add__(self, other: "Vector") -> "Vector":
        self._check_same_dim(other)
        return Vector(*(a + b for a, b in zip(self._components, other._components)))

    def __sub__(self, other: "Vector") -> "Vector":
        self._check_same_dim(other)
        return Vector(*(a - b for a, b in zip(self._components, other._components)))

    def __mul__(self, scalar: float) -> "Vector":
        return Vector(*(a * scalar for a in self._components))

    def __rmul__(self, scalar: float) -> "Vector":
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> "Vector":
        if scalar == 0:
            raise ZeroDivisionError("cannot divide vector by zero")
        return Vector(*(a / scalar for a in self._components))

    def __neg__(self) -> "Vector":
        return Vector(*(-a for a in self._components))

    # --- geometric operations -------------------------------------------------

    def dot(self, other: "Vector") -> float:
        self._check_same_dim(other)
        return sum(a * b for a, b in zip(self._components, other._components))

    def length_squared(self) -> float:
        """Squared magnitude. Cheaper than length(); use for comparisons."""
        return sum(a * a for a in self._components)

    def length(self) -> float:
        return math.sqrt(self.length_squared())

    def normalized(self) -> "Vector":
        """Return a unit vector in the same direction.

        The zero vector has no direction, so normalizing it returns the zero
        vector (a deliberate, safe choice rather than raising).
        """
        mag = self.length()
        if mag == 0:
            return self
        return self / mag

    def distance_squared_to(self, other: "Vector") -> float:
        self._check_same_dim(other)
        return sum((a - b) ** 2 for a, b in zip(self._components, other._components))

    def distance_to(self, other: "Vector") -> float:
        return math.sqrt(self.distance_squared_to(other))

    # --- equality / representation --------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return self._components == other._components

    def __hash__(self) -> int:
        return hash(self._components)

    def __repr__(self) -> str:
        inner = ", ".join(repr(c) for c in self._components)
        return f"Vector({inner})"
