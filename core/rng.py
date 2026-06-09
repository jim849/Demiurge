"""Injectable, reproducible random number generator.

Design decisions (see PLAN.md, Milestone 1):
- **Dependency injection** (iron laws 7, 8): the core never touches the module-
  global `random`. Every random draw comes from an explicit Rng instance that is
  passed in. This is what makes a fixed seed actually reproduce a run.
- **Named sub-streams** via `spawn(name)`: a child Rng is derived deterministically
  from (parent seed, name) using a stable hash. Because the derivation does NOT
  depend on how much the parent stream has been consumed, changing the number of
  draws in one part of the simulation (e.g. mutation) cannot shift the random
  sequence seen elsewhere (e.g. world generation). This keeps reproducibility
  robust as the code evolves.

The underlying generator is the standard library's Mersenne Twister
(`random.Random`), whose sequence is stable across platforms and Python versions
for a given seed -- important for cross-platform reproducibility (iron law 9).
"""

from __future__ import annotations

import hashlib
import random
from typing import MutableSequence, Sequence, TypeVar

T = TypeVar("T")


def _derive_seed(parent_seed: int, name: str) -> int:
    """Deterministically derive a child seed from a parent seed and a name.

    Uses SHA-256 (not Python's salted built-in hash) so the result is stable
    across processes, platforms and runs.
    """
    payload = f"{parent_seed}:{name}".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    return int.from_bytes(digest[:8], "big")


class Rng:
    """A seeded, injectable random source with named sub-streams."""

    __slots__ = ("_seed", "_name", "_rand")

    def __init__(self, seed: int, _name: str = "root") -> None:
        self._seed = int(seed)
        self._name = _name
        # Independent instance -- never the module-global random.
        self._rand = random.Random(self._seed)

    # --- identity -------------------------------------------------------------

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def name(self) -> str:
        return self._name

    def spawn(self, name: str) -> "Rng":
        """Derive an independent, named child stream.

        Same (parent seed, name) always yields the same child stream, regardless
        of how much this parent has been consumed.
        """
        child_seed = _derive_seed(self._seed, name)
        child_name = f"{self._name}/{name}"
        return Rng(child_seed, _name=child_name)

    # --- draws ----------------------------------------------------------------

    def random(self) -> float:
        """Float in [0.0, 1.0)."""
        return self._rand.random()

    def uniform(self, a: float, b: float) -> float:
        """Float uniformly in [a, b]."""
        return self._rand.uniform(a, b)

    def gauss(self, mu: float, sigma: float) -> float:
        """Gaussian (normal) draw -- natural for mutation steps."""
        return self._rand.gauss(mu, sigma)

    def randint(self, a: int, b: int) -> int:
        """Integer uniformly in [a, b] (both inclusive)."""
        return self._rand.randint(a, b)

    def boolean(self, p: float = 0.5) -> bool:
        """True with probability p. Used for conflict tie-breaks and mutation gates."""
        if not 0.0 <= p <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        return self._rand.random() < p

    def choice(self, seq: Sequence[T]) -> T:
        """Pick one element uniformly. `seq` must be order-stable (no sets)."""
        return self._rand.choice(seq)

    def shuffle(self, seq: MutableSequence[T]) -> None:
        """Shuffle a mutable sequence in place."""
        self._rand.shuffle(seq)

    def __repr__(self) -> str:
        return f"Rng(seed={self._seed}, name={self._name!r})"
