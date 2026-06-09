"""Tests for core.vector.Vector.

Headless, pure-logic tests (iron law: core must be testable without graphics).
"""

import math

import pytest

from core.vector import Vector


# --- construction ------------------------------------------------------------

def test_construction_and_components():
    v = Vector(1.0, 2.0, 3.0)
    assert v.components == (1.0, 2.0, 3.0)
    assert v.dim == 3
    assert len(v) == 3


def test_construction_coerces_to_float():
    v = Vector(1, 2)
    assert v.components == (1.0, 2.0)
    assert all(isinstance(c, float) for c in v)


def test_empty_construction_raises():
    with pytest.raises(ValueError):
        Vector()


def test_from_iterable():
    assert Vector.from_iterable([4, 5, 6]) == Vector(4, 5, 6)


def test_zero():
    assert Vector.zero(2) == Vector(0.0, 0.0)
    assert Vector.zero(3) == Vector(0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        Vector.zero(0)


# --- access ------------------------------------------------------------------

def test_named_accessors():
    v = Vector(7.0, 8.0, 9.0)
    assert v.x == 7.0
    assert v.y == 8.0
    assert v.z == 9.0


def test_missing_named_accessors_raise():
    v = Vector(1.0)
    with pytest.raises(AttributeError):
        _ = v.y
    with pytest.raises(AttributeError):
        _ = v.z


def test_indexing_and_iteration():
    v = Vector(1.0, 2.0)
    assert v[0] == 1.0
    assert v[1] == 2.0
    assert list(v) == [1.0, 2.0]


# --- immutability ------------------------------------------------------------

def test_immutable_setattr():
    v = Vector(1.0, 2.0)
    with pytest.raises(AttributeError):
        v.x = 5.0  # type: ignore[misc]
    with pytest.raises(AttributeError):
        v._components = (9.0,)  # type: ignore[attr-defined]


# --- arithmetic --------------------------------------------------------------

def test_add_sub():
    a = Vector(1.0, 2.0)
    b = Vector(3.0, 4.0)
    assert a + b == Vector(4.0, 6.0)
    assert b - a == Vector(2.0, 2.0)


def test_scalar_mul_both_sides_and_div():
    v = Vector(2.0, 4.0)
    assert v * 2 == Vector(4.0, 8.0)
    assert 2 * v == Vector(4.0, 8.0)
    assert v / 2 == Vector(1.0, 2.0)


def test_div_by_zero_raises():
    with pytest.raises(ZeroDivisionError):
        Vector(1.0, 2.0) / 0


def test_negation():
    assert -Vector(1.0, -2.0) == Vector(-1.0, 2.0)


def test_dim_mismatch_raises():
    a = Vector(1.0, 2.0)
    b = Vector(1.0, 2.0, 3.0)
    with pytest.raises(ValueError):
        _ = a + b
    with pytest.raises(ValueError):
        _ = a.dot(b)
    with pytest.raises(ValueError):
        _ = a.distance_to(b)


# --- geometry ----------------------------------------------------------------

def test_dot():
    assert Vector(1.0, 2.0, 3.0).dot(Vector(4.0, 5.0, 6.0)) == 32.0


def test_length_and_length_squared():
    v = Vector(3.0, 4.0)
    assert v.length_squared() == 25.0
    assert v.length() == 5.0


def test_normalized_unit_length():
    v = Vector(3.0, 4.0).normalized()
    assert math.isclose(v.length(), 1.0)
    assert math.isclose(v.x, 0.6)
    assert math.isclose(v.y, 0.8)


def test_normalized_zero_vector_returns_zero():
    z = Vector.zero(2)
    assert z.normalized() == z


def test_distance():
    a = Vector(0.0, 0.0)
    b = Vector(3.0, 4.0)
    assert a.distance_squared_to(b) == 25.0
    assert a.distance_to(b) == 5.0


# --- dimension-agnostic proof (3D works exactly the same) --------------------

def test_works_in_3d():
    a = Vector(1.0, 0.0, 0.0)
    b = Vector(0.0, 1.0, 0.0)
    assert (a + b) == Vector(1.0, 1.0, 0.0)
    assert a.dot(b) == 0.0
    assert math.isclose(Vector(2.0, 0.0, 0.0).normalized().length(), 1.0)


# --- equality / hashing ------------------------------------------------------

def test_equality_and_hash():
    assert Vector(1.0, 2.0) == Vector(1.0, 2.0)
    assert Vector(1.0, 2.0) != Vector(2.0, 1.0)
    assert Vector(1.0, 2.0) != "not a vector"
    # hashable -> usable in sets/dicts
    assert len({Vector(1.0, 2.0), Vector(1.0, 2.0)}) == 1


def test_repr_roundtrip():
    v = Vector(1.5, 2.5)
    assert repr(v) == "Vector(1.5, 2.5)"
