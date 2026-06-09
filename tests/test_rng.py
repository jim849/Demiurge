"""Tests for core.rng.Rng.

Reproducibility is the whole point of this module, so the tests focus on:
same seed -> same sequence, different seed -> different sequence, and sub-streams
being independent of each other and of parent consumption.
"""

import pytest

from core.rng import Rng


# --- reproducibility ---------------------------------------------------------

def test_same_seed_same_sequence():
    a = Rng(42)
    b = Rng(42)
    assert [a.random() for _ in range(10)] == [b.random() for _ in range(10)]


def test_different_seed_different_sequence():
    a = Rng(1)
    b = Rng(2)
    assert [a.random() for _ in range(10)] != [b.random() for _ in range(10)]


def test_does_not_touch_global_random():
    import random as global_random

    global_random.seed(123)
    before = global_random.random()

    global_random.seed(123)
    rng = Rng(999)
    _ = [rng.random() for _ in range(5)]
    after = global_random.random()

    # Draws from Rng must not advance the module-global random stream.
    assert before == after


# --- draw helpers ------------------------------------------------------------

def test_uniform_within_bounds():
    rng = Rng(7)
    for _ in range(100):
        v = rng.uniform(-2.0, 5.0)
        assert -2.0 <= v <= 5.0


def test_randint_within_bounds_inclusive():
    rng = Rng(7)
    seen = {rng.randint(1, 3) for _ in range(200)}
    assert seen == {1, 2, 3}


def test_boolean_probability_extremes():
    rng = Rng(7)
    assert all(rng.boolean(1.0) for _ in range(50))
    assert not any(rng.boolean(0.0) for _ in range(50))


def test_boolean_invalid_probability_raises():
    rng = Rng(7)
    with pytest.raises(ValueError):
        rng.boolean(1.5)
    with pytest.raises(ValueError):
        rng.boolean(-0.1)


def test_choice_returns_member():
    rng = Rng(7)
    options = ["a", "b", "c"]
    for _ in range(50):
        assert rng.choice(options) in options


def test_shuffle_in_place_is_permutation():
    rng = Rng(7)
    data = list(range(10))
    rng.shuffle(data)
    assert sorted(data) == list(range(10))


def test_gauss_is_reproducible():
    a = Rng(7)
    b = Rng(7)
    assert [a.gauss(0.0, 1.0) for _ in range(5)] == [b.gauss(0.0, 1.0) for _ in range(5)]


# --- sub-streams -------------------------------------------------------------

def test_spawn_is_deterministic():
    parent_a = Rng(100)
    parent_b = Rng(100)
    ca = parent_a.spawn("mutation")
    cb = parent_b.spawn("mutation")
    assert [ca.random() for _ in range(10)] == [cb.random() for _ in range(10)]


def test_different_named_substreams_differ():
    parent = Rng(100)
    mutation = parent.spawn("mutation")
    world = parent.spawn("world")
    assert [mutation.random() for _ in range(10)] != [world.random() for _ in range(10)]


def test_substream_independent_of_parent_consumption():
    # Spawn before consuming the parent.
    p1 = Rng(100)
    early = p1.spawn("mutation")

    # Consume the parent heavily, THEN spawn the same-named child.
    p2 = Rng(100)
    _ = [p2.random() for _ in range(1000)]
    late = p2.spawn("mutation")

    # The child stream must be identical regardless of parent consumption.
    assert [early.random() for _ in range(10)] == [late.random() for _ in range(10)]


def test_substream_differs_from_parent():
    parent = Rng(100)
    child = parent.spawn("child")
    parent_seq = [parent.random() for _ in range(10)]
    child_seq = [child.random() for _ in range(10)]
    assert parent_seq != child_seq


def test_spawn_metadata():
    parent = Rng(100)
    child = parent.spawn("mutation")
    assert child.name == "root/mutation"
    grandchild = child.spawn("step")
    assert grandchild.name == "root/mutation/step"
