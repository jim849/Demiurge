"""Tests for core.genome and the config genome schema.

Covers the generic engine (GeneSpec/Gene/Chromosome/Genome) plus a sanity check
that the real config schema builds correctly.
"""

import pytest

from core.genome import ChromosomeSpec, Gene, GeneSpec, Genome
from core.rng import Rng
import config


# --- GeneSpec ----------------------------------------------------------------

def test_genespec_validates():
    with pytest.raises(ValueError):
        GeneSpec("bad", 1.0, 0.0, 0.1, 0.1)  # min > max
    with pytest.raises(ValueError):
        GeneSpec("bad", 0.0, 1.0, -0.1, 0.1)  # negative step
    with pytest.raises(ValueError):
        GeneSpec("bad", 0.0, 1.0, 0.1, 1.5)  # prob out of range


def test_genespec_clamp_and_contains():
    spec = GeneSpec("g", 0.0, 1.0, 0.1, 0.1)
    assert spec.clamp(-5.0) == 0.0
    assert spec.clamp(5.0) == 1.0
    assert spec.clamp(0.5) == 0.5
    assert spec.contains(0.5)
    assert not spec.contains(1.5)


def test_genespec_random_value_in_range():
    spec = GeneSpec("g", 0.2, 0.8, 0.1, 0.1)
    rng = Rng(1)
    for _ in range(100):
        assert spec.contains(spec.random_value(rng))


# --- Gene --------------------------------------------------------------------

def test_gene_set_validates():
    g = Gene(GeneSpec("g", 0.0, 1.0, 0.1, 0.1), 0.5)
    g.set(0.9)
    assert g.value == 0.9
    with pytest.raises(ValueError):
        g.set(2.0)


def test_gene_construction_out_of_range_raises():
    with pytest.raises(ValueError):
        Gene(GeneSpec("g", 0.0, 1.0, 0.1, 0.1), 5.0)


def test_gene_mutate_stays_in_range():
    # High step + certain mutation; must never escape [min, max].
    spec = GeneSpec("g", 0.0, 1.0, 10.0, 1.0)
    rng = Rng(3)
    for _ in range(200):
        g = Gene(spec, 0.5)
        g.mutate(rng)
        assert spec.contains(g.value)


def test_gene_mutate_prob_zero_never_changes():
    spec = GeneSpec("g", 0.0, 1.0, 0.5, 0.0)
    rng = Rng(3)
    g = Gene(spec, 0.5)
    for _ in range(50):
        g.mutate(rng)
    assert g.value == 0.5


# --- Genome construction & access --------------------------------------------

_SCHEMA = (
    ChromosomeSpec("body", (GeneSpec("size", 0.0, 1.0, 0.1, 0.5), GeneSpec("speed", 0.0, 1.0, 0.1, 0.5))),
    ChromosomeSpec("brain", (GeneSpec("aggression", 0.0, 1.0, 0.1, 0.5),)),
)


def test_random_genome_has_all_genes_in_range():
    rng = Rng(5)
    g = Genome.random(_SCHEMA, rng)
    assert set(g.gene_names()) == {"size", "speed", "aggression"}
    for name in g.gene_names():
        assert 0.0 <= g.get(name) <= 1.0


def test_get_set_by_name():
    g = Genome.random(_SCHEMA, Rng(5))
    g.set("size", 0.42)
    assert g.get("size") == 0.42
    with pytest.raises(ValueError):
        g.set("size", 9.0)  # out of range
    with pytest.raises(KeyError):
        g.get("nonexistent")


def test_from_values_requires_exact_gene_set():
    good = {"size": 0.1, "speed": 0.2, "aggression": 0.3}
    g = Genome.from_values(_SCHEMA, good)
    assert g.as_dict() == good
    with pytest.raises(ValueError):
        Genome.from_values(_SCHEMA, {"size": 0.1})  # missing
    with pytest.raises(ValueError):
        Genome.from_values(_SCHEMA, {**good, "extra": 0.5})  # extra


def test_duplicate_gene_name_rejected():
    schema = (
        ChromosomeSpec("a", (GeneSpec("dup", 0.0, 1.0, 0.1, 0.5),)),
        ChromosomeSpec("b", (GeneSpec("dup", 0.0, 1.0, 0.1, 0.5),)),
    )
    with pytest.raises(ValueError):
        Genome.random(schema, Rng(5))


# --- copy independence -------------------------------------------------------

def test_copy_is_independent():
    parent = Genome.from_values(_SCHEMA, {"size": 0.1, "speed": 0.2, "aggression": 0.3})
    child = parent.copy()
    child.set("size", 0.9)
    assert parent.get("size") == 0.1  # parent unchanged
    assert child.get("size") == 0.9


# --- reproduction (copy + mutate) reproducibility ----------------------------

def test_copy_then_mutate_is_reproducible():
    parent = Genome.from_values(_SCHEMA, {"size": 0.5, "speed": 0.5, "aggression": 0.5})

    child_a = parent.copy().mutate(Rng(77))
    child_b = parent.copy().mutate(Rng(77))
    assert child_a.as_dict() == child_b.as_dict()
    # parent untouched by mutation
    assert parent.as_dict() == {"size": 0.5, "speed": 0.5, "aggression": 0.5}


# --- inspection views --------------------------------------------------------

def test_nested_dict_mirrors_structure():
    g = Genome.from_values(_SCHEMA, {"size": 0.1, "speed": 0.2, "aggression": 0.3})
    assert g.as_nested_dict() == {
        "body": {"size": 0.1, "speed": 0.2},
        "brain": {"aggression": 0.3},
    }


# --- real config schema sanity ----------------------------------------------

def test_config_schema_builds_with_ten_genes():
    g = Genome.random(config.GENOME_SCHEMA, Rng(config.DEFAULT_SEED))
    expected = {
        "size", "speed", "sense_range",
        "diet", "repro_threshold", "metabolism", "offspring_investment",
        "aggression", "fear", "exploration",
    }
    assert set(g.gene_names()) == expected
    assert len(g.gene_names()) == 10


def test_config_schema_chromosome_grouping():
    g = Genome.random(config.GENOME_SCHEMA, Rng(config.DEFAULT_SEED))
    nested = g.as_nested_dict()
    assert set(nested) == {"body", "metabolism", "brain"}
    # size and speed deliberately co-located (future linkage).
    assert "size" in nested["body"] and "speed" in nested["body"]
