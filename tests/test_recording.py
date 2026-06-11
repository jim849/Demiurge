"""Tests for the time-series recorder: it must compress each WorldSnapshot to
one aggregate row, count diet buckets at the injected thresholds, survive an
empty world, and round-trip its rows through CSV (iron laws 6, 10, 11)."""

import csv

import pytest

from core.recording import TickStats, TimeSeriesRecorder
from core.vector import Vector
from core.world import AgentSnapshot, PlantSnapshot, WorldSnapshot


def _agent(id_: int, *, diet: float, size: float, energy: float, generation: int) -> AgentSnapshot:
    return AgentSnapshot(
        id=id_,
        position=Vector(0.0, 0.0),
        heading=Vector(1.0, 0.0),
        body_radius=size * 10.0,
        energy=energy,
        size=size,
        diet=diet,
        alive=True,
        generation=generation,
    )


def _snapshot(tick: int, agents, n_plants: int = 0) -> WorldSnapshot:
    plants = tuple(
        PlantSnapshot(id=i, position=Vector(0.0, 0.0), body_radius=1.0)
        for i in range(n_plants)
    )
    return WorldSnapshot(
        tick=tick, size=Vector(100.0, 100.0), agents=tuple(agents), plants=plants
    )


def test_records_one_row_per_tick():
    rec = TimeSeriesRecorder()
    rec.record_tick(_snapshot(0, [_agent(1, diet=0.1, size=0.3, energy=10.0, generation=0)]))
    rec.record_tick(_snapshot(1, [_agent(1, diet=0.1, size=0.3, energy=12.0, generation=0)]))
    assert [r.tick for r in rec.rows] == [0, 1]


def test_aggregates_are_correct():
    agents = [
        _agent(1, diet=0.1, size=0.2, energy=10.0, generation=0),
        _agent(2, diet=0.5, size=0.4, energy=20.0, generation=3),
        _agent(3, diet=0.9, size=0.6, energy=30.0, generation=1),
    ]
    rec = TimeSeriesRecorder()
    rec.record_tick(_snapshot(7, agents, n_plants=42))
    row = rec.rows[0]
    assert row.tick == 7
    assert row.n_agents == 3
    assert row.n_plants == 42
    assert row.mean_energy == pytest.approx(20.0)
    assert row.mean_diet == pytest.approx(0.5)
    assert row.mean_size == pytest.approx(0.4)
    assert row.max_generation == 3


def test_diet_buckets_use_default_thresholds():
    # herb < 0.3, carn >= 0.6, mid in between (boundaries: 0.3 -> mid, 0.6 -> carn)
    agents = [
        _agent(1, diet=0.0, size=0.3, energy=1.0, generation=0),
        _agent(2, diet=0.29, size=0.3, energy=1.0, generation=0),
        _agent(3, diet=0.3, size=0.3, energy=1.0, generation=0),
        _agent(4, diet=0.59, size=0.3, energy=1.0, generation=0),
        _agent(5, diet=0.6, size=0.3, energy=1.0, generation=0),
        _agent(6, diet=1.0, size=0.3, energy=1.0, generation=0),
    ]
    rec = TimeSeriesRecorder()
    rec.record_tick(_snapshot(0, agents))
    row = rec.rows[0]
    assert (row.n_herb, row.n_mid, row.n_carn) == (2, 2, 2)
    assert row.n_herb + row.n_mid + row.n_carn == row.n_agents


def test_diet_thresholds_are_injectable():
    agents = [_agent(i, diet=d, size=0.3, energy=1.0, generation=0)
              for i, d in enumerate([0.1, 0.4, 0.8])]
    rec = TimeSeriesRecorder(herb_max=0.5, carn_min=0.7)
    rec.record_tick(_snapshot(0, agents))
    row = rec.rows[0]
    assert (row.n_herb, row.n_mid, row.n_carn) == (2, 0, 1)


def test_empty_world_records_zeros():
    rec = TimeSeriesRecorder()
    rec.record_tick(_snapshot(5, [], n_plants=3))
    row = rec.rows[0]
    assert row.n_agents == 0
    assert row.n_plants == 3
    assert row.mean_energy == 0.0
    assert row.mean_diet == 0.0
    assert row.mean_size == 0.0
    assert row.max_generation == 0
    assert (row.n_herb, row.n_mid, row.n_carn) == (0, 0, 0)


def test_invalid_thresholds_rejected():
    with pytest.raises(ValueError):
        TimeSeriesRecorder(herb_max=0.7, carn_min=0.6)
    with pytest.raises(ValueError):
        TimeSeriesRecorder(herb_max=-0.1)
    with pytest.raises(ValueError):
        TimeSeriesRecorder(carn_min=1.5)


def test_to_csv_round_trips(tmp_path):
    agents = [
        _agent(1, diet=0.1, size=0.2, energy=10.0, generation=0),
        _agent(2, diet=0.9, size=0.6, energy=30.0, generation=2),
    ]
    rec = TimeSeriesRecorder()
    rec.record_tick(_snapshot(0, agents, n_plants=5))
    rec.record_tick(_snapshot(1, [], n_plants=6))

    out = rec.to_csv(tmp_path / "sub" / "series.csv")
    assert out.exists()

    with out.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert rows[0]["tick"] == "0"
    assert rows[0]["n_agents"] == "2"
    assert rows[0]["n_plants"] == "5"
    assert rows[0]["max_generation"] == "2"
    assert rows[1]["tick"] == "1"
    assert rows[1]["n_agents"] == "0"

    # header matches the dataclass field order exactly
    expected_header = [
        "tick", "n_agents", "n_plants", "mean_energy", "mean_diet",
        "mean_size", "max_generation", "n_herb", "n_mid", "n_carn",
    ]
    assert list(rows[0].keys()) == expected_header
