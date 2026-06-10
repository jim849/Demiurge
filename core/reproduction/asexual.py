"""Asexual reproduction: the v1 strategy -- copy the genome, then mutate.

One parent, one child. The child is a deep copy of the parent's genome with each
gene independently mutated (per-gene probability + step from the genome schema, set
in config -- iron law 10). This is the simplest heritable-with-variation scheme:
offspring resemble the parent, small mutations supply the variation selection acts
on. Sexual recombination (M3) is a different Reproducer, not a change here.
"""

from __future__ import annotations

from core.genome import Genome
from core.reproduction.base import Reproducer
from core.rng import Rng


class AsexualReproduction(Reproducer):
    """Copy + mutate: `child = parent.copy().mutate(rng)`."""

    def reproduce(self, parent_genome: Genome, rng: Rng) -> Genome:
        # copy() first so the parent's own genome is never touched; mutate() walks
        # every gene and rolls its per-gene mutation chance against the injected rng.
        return parent_genome.copy().mutate(rng)
