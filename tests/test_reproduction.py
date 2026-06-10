"""Tests for core.reproduction -- the swappable genetics strategy (v1: asexual)."""

from core.genome import Genome
from core.reproduction.asexual import AsexualReproduction
from core.reproduction.base import Reproducer
from core.rng import Rng
import config


def _genome(seed=1) -> Genome:
    return Genome.random(config.GENOME_SCHEMA, Rng(seed))


def test_asexual_is_a_reproducer():
    assert isinstance(AsexualReproduction(), Reproducer)


def test_child_is_a_genome_with_the_same_genes():
    parent = _genome()
    child = AsexualReproduction().reproduce(parent, Rng(7))
    assert isinstance(child, Genome)
    assert child.as_dict().keys() == parent.as_dict().keys()


def test_parent_genome_is_not_mutated_in_place():
    parent = _genome()
    before = parent.as_dict()
    AsexualReproduction().reproduce(parent, Rng(7))
    assert parent.as_dict() == before  # parent lives on, untouched


def test_child_is_an_independent_object():
    parent = _genome()
    child = AsexualReproduction().reproduce(parent, Rng(7))
    assert child is not parent
    # editing the child must not reach back into the parent
    name = next(iter(parent.as_dict()))
    child.set(name, parent.get(name) * 0.5 + 0.05)
    assert child.get(name) != parent.get(name)


def test_reproduction_is_deterministic():
    parent = _genome()
    a = AsexualReproduction().reproduce(parent, Rng(42)).as_dict()
    b = AsexualReproduction().reproduce(parent, Rng(42)).as_dict()
    assert a == b  # same parent + same seed -> identical child


def test_child_values_stay_in_gene_range():
    parent = _genome()
    # many draws: every mutated value must remain clamped to its gene's [min, max]
    for s in range(50):
        child = AsexualReproduction().reproduce(parent, Rng(s))
        nested = child.as_nested_dict()
        for chrom in config.GENOME_SCHEMA:
            for gene in chrom.genes:
                v = nested[chrom.name][gene.name]
                assert gene.min_value <= v <= gene.max_value
