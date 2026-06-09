"""Genome: the core, central data structure of the whole project.

Everything (evolution, mutation, manual creator edits, future neural-network
weights, future sexual recombination) hangs off this structure, so it is built
generically from day one.

Design decisions (see PLAN.md, Milestone 1):
- **Engine vs schema split** (iron law 10): this module is a *generic* gene/
  chromosome/genome engine. The actual 10-gene schema (names, ranges, mutation
  steps/probabilities) lives in `config.py` and is passed in. Tuning balance
  means editing config, never this file. (Dependency is one-directional:
  config -> genome; this module never imports config.)
- **Genome = list of chromosomes** from day one, so future sexual recombination
  and linkage need no restructuring. v1 asexual reproduction just copies + mutates.
- **Mutable values + explicit `copy()`**: reproduction is `parent.copy()` then
  `mutate(rng)`; a creator editing a live agent's gene just calls `set()`.
- **`set()` raises on out-of-range** (explicit edits must be correct), while
  **`mutate()` clamps** internally (a Gaussian step may overshoot a bound).
- **Genotype/phenotype separation**: a Genome holds only abstract gene values.
  Translating them into actual abilities is `phenotype.py`'s job, not this one.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.rng import Rng


@dataclass(frozen=True)
class GeneSpec:
    """Immutable template for one gene: its bounds and mutation parameters."""

    name: str
    min_value: float
    max_value: float
    mutation_step: float  # std dev of the Gaussian mutation step
    mutation_prob: float  # per-reproduction probability this gene mutates

    def __post_init__(self) -> None:
        if self.min_value > self.max_value:
            raise ValueError(
                f"gene {self.name!r}: min_value {self.min_value} > max_value {self.max_value}"
            )
        if self.mutation_step < 0:
            raise ValueError(f"gene {self.name!r}: mutation_step must be >= 0")
        if not 0.0 <= self.mutation_prob <= 1.0:
            raise ValueError(f"gene {self.name!r}: mutation_prob must be in [0, 1]")

    def clamp(self, value: float) -> float:
        """Clamp a value into this gene's legal range."""
        return max(self.min_value, min(self.max_value, value))

    def contains(self, value: float) -> bool:
        return self.min_value <= value <= self.max_value

    def random_value(self, rng: Rng) -> float:
        """A uniformly random legal value (for initial random genomes)."""
        return rng.uniform(self.min_value, self.max_value)


@dataclass(frozen=True)
class ChromosomeSpec:
    """Immutable template for one chromosome: an ordered group of gene specs."""

    name: str
    genes: tuple[GeneSpec, ...]


class Gene:
    """A live gene: its (immutable) spec plus a current, mutable value."""

    __slots__ = ("spec", "_value")

    def __init__(self, spec: GeneSpec, value: float) -> None:
        self.spec = spec
        self._value = 0.0
        self.set(value)  # validated assignment

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def value(self) -> float:
        return self._value

    def set(self, value: float) -> None:
        """Set the value, raising if it falls outside the legal range."""
        value = float(value)
        if not self.spec.contains(value):
            raise ValueError(
                f"gene {self.spec.name!r}: value {value} outside "
                f"[{self.spec.min_value}, {self.spec.max_value}]"
            )
        self._value = value

    def mutate(self, rng: Rng) -> None:
        """Maybe perturb the value by a clamped Gaussian step (in place)."""
        if rng.boolean(self.spec.mutation_prob):
            stepped = self._value + rng.gauss(0.0, self.spec.mutation_step)
            self._value = self.spec.clamp(stepped)

    def copy(self) -> "Gene":
        # spec is frozen/immutable, so it can be shared safely.
        return Gene(self.spec, self._value)

    def __repr__(self) -> str:
        return f"Gene({self.spec.name!r}={self._value})"


class Chromosome:
    """A named, ordered group of live genes."""

    __slots__ = ("name", "genes")

    def __init__(self, name: str, genes: list[Gene]) -> None:
        self.name = name
        self.genes = genes

    def copy(self) -> "Chromosome":
        return Chromosome(self.name, [g.copy() for g in self.genes])

    def __repr__(self) -> str:
        return f"Chromosome({self.name!r}, {self.genes!r})"


class Genome:
    """An agent's full chromosome set, with by-name gene access.

    Gene names must be unique across the whole genome (so get/set by name is
    unambiguous), even though genes are grouped into chromosomes.
    """

    __slots__ = ("chromosomes", "_index")

    def __init__(self, chromosomes: list[Chromosome]) -> None:
        self.chromosomes = chromosomes
        # Build a flat name -> Gene index for O(1) get/set by name.
        index: dict[str, Gene] = {}
        for chrom in chromosomes:
            for gene in chrom.genes:
                if gene.name in index:
                    raise ValueError(f"duplicate gene name across genome: {gene.name!r}")
                index[gene.name] = gene
        self._index = index

    # --- construction from a schema ------------------------------------------

    @classmethod
    def random(cls, schema: tuple[ChromosomeSpec, ...], rng: Rng) -> "Genome":
        """Build a genome with uniformly random legal values from a schema."""
        chromosomes = [
            Chromosome(cspec.name, [Gene(gspec, gspec.random_value(rng)) for gspec in cspec.genes])
            for cspec in schema
        ]
        return cls(chromosomes)

    @classmethod
    def from_values(
        cls, schema: tuple[ChromosomeSpec, ...], values: dict[str, float]
    ) -> "Genome":
        """Build a genome from explicit gene values (the creator's 'make from
        given genes' path). Every schema gene must be supplied, and no extras."""
        expected = {gspec.name for cspec in schema for gspec in cspec.genes}
        provided = set(values)
        if provided != expected:
            missing = expected - provided
            extra = provided - expected
            raise ValueError(f"value mismatch: missing={sorted(missing)}, extra={sorted(extra)}")
        chromosomes = [
            Chromosome(cspec.name, [Gene(gspec, values[gspec.name]) for gspec in cspec.genes])
            for cspec in schema
        ]
        return cls(chromosomes)

    # --- low-level gene API (no world knowledge) ------------------------------

    def get(self, gene_name: str) -> float:
        """Read a gene's value by name."""
        return self._index[gene_name].value

    def set(self, gene_name: str, value: float) -> None:
        """Write a gene's value by name (range-validated, raises if out of range)."""
        self._index[gene_name].set(value)

    def gene_names(self) -> list[str]:
        return list(self._index.keys())

    def copy(self) -> "Genome":
        """Deep copy: independent genome with the same values (reproduction step 1)."""
        return Genome([c.copy() for c in self.chromosomes])

    def mutate(self, rng: Rng) -> "Genome":
        """Mutate every gene in place (reproduction step 2). Returns self for chaining."""
        for chrom in self.chromosomes:
            for gene in chrom.genes:
                gene.mutate(rng)
        return self

    # --- inspection (for selection display, recording) ------------------------

    def as_dict(self) -> dict[str, float]:
        """Flat {gene_name: value} view."""
        return {name: gene.value for name, gene in self._index.items()}

    def as_nested_dict(self) -> dict[str, dict[str, float]]:
        """{chromosome_name: {gene_name: value}} view (mirrors structure)."""
        return {
            chrom.name: {gene.name: gene.value for gene in chrom.genes}
            for chrom in self.chromosomes
        }

    def __repr__(self) -> str:
        return f"Genome({self.chromosomes!r})"
