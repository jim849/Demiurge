"""Reproduction strategy interface: the fixed contract for making a child genome.

Design decisions (see PLAN.md, Milestone 0 gene system + Milestone 3):
- **Genetics only.** A Reproducer maps parent genome(s) + rng -> a child Genome. It
  does NOT decide *when* an agent reproduces, *how much* energy the child gets, or
  *where* it is placed -- those are world/energy concerns handled in the World's
  resolve phase. Keeping the strategy this narrow is what lets M3 drop in sexual
  recombination without touching the World (iron law 5).
- **Asexual now, sexual later.** v1's single parent (`AsexualReproduction`) is the
  one-parent case; the interface is written so a future multi-parent strategy is a
  new implementation, not a re-design.
- **RNG is injected (iron law 8).** All randomness (which genes mutate, by how much,
  and -- later -- recombination crossover points) draws from the passed-in Rng, never
  module-global `random`, so reproduction stays reproducible.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.genome import Genome
from core.rng import Rng


class Reproducer(ABC):
    """Strategy that produces a child genome from a parent genome."""

    @abstractmethod
    def reproduce(self, parent_genome: Genome, rng: Rng) -> Genome:
        """Return a new, independent child Genome derived from `parent_genome`.

        Must not mutate `parent_genome` in place: the parent lives on. Implementations
        copy first, then apply their genetics (mutation, and later recombination).
        """
        raise NotImplementedError
