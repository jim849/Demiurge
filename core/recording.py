"""Data-recording interface -- a clean hook, stubbed from day one (iron law 6).

We don't record anything yet, but the *seam* exists now so that adding logging,
metrics, or a full event store later means writing a new `Recorder` and injecting
it -- never editing the world loop. The World calls `record_tick` once per tick
with the same immutable snapshot the renderer sees, so a recorder can persist
history without ever touching live `Agent` state (iron laws 1, 2).

`Recorder` is deliberately tiny. Richer signals (births, deaths, predation events)
get added as explicit methods when the milestones that produce them land; until
then the per-tick snapshot is enough and keeps the interface honest.
"""

from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from statistics import fmean
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a circular import; only needed for type hints
    from core.world import WorldSnapshot


class Recorder(ABC):
    """Sink for per-tick simulation data. Implementations decide what to persist."""

    @abstractmethod
    def record_tick(self, snapshot: "WorldSnapshot") -> None:
        """Called once per tick with the world's immutable snapshot."""
        raise NotImplementedError


class NullRecorder(Recorder):
    """The default: records nothing. Keeps the world loop unconditional (no
    `if recorder is not None` checks scattered around)."""

    def record_tick(self, snapshot: "WorldSnapshot") -> None:  # noqa: D401
        return None


@dataclass(frozen=True, slots=True)
class TickStats:
    """One row of the population time series: the world compressed to aggregates.

    Per-agent detail is deliberately dropped here -- a recorder that kept every
    AgentSnapshot for every tick would grow without bound. This is the cheap,
    always-on summary; richer per-agent or event logging can be layered on later
    behind its own Recorder.
    """

    tick: int
    n_agents: int
    n_plants: int
    mean_energy: float
    mean_diet: float
    mean_size: float
    max_generation: int
    n_herb: int
    n_mid: int
    n_carn: int


class TimeSeriesRecorder(Recorder):
    """Accumulates one `TickStats` row per tick in memory; exports to CSV.

    Diet-bucket thresholds are injected (iron law 10): an agent counts as a
    herbivore when `diet < herb_max`, a carnivore when `diet >= carn_min`, and
    everything between is a mid/omnivore. Defaults mirror the display constants
    used elsewhere (herb < 0.3, carn >= 0.6).
    """

    def __init__(self, *, herb_max: float = 0.3, carn_min: float = 0.6) -> None:
        if not 0.0 <= herb_max <= carn_min <= 1.0:
            raise ValueError("require 0 <= herb_max <= carn_min <= 1")
        self.herb_max = herb_max
        self.carn_min = carn_min
        self.rows: list[TickStats] = []

    def record_tick(self, snapshot: "WorldSnapshot") -> None:
        agents = snapshot.agents
        n = len(agents)
        if n == 0:
            self.rows.append(
                TickStats(
                    tick=snapshot.tick,
                    n_agents=0,
                    n_plants=len(snapshot.plants),
                    mean_energy=0.0,
                    mean_diet=0.0,
                    mean_size=0.0,
                    max_generation=0,
                    n_herb=0,
                    n_mid=0,
                    n_carn=0,
                )
            )
            return
        diets = [a.diet for a in agents]
        n_herb = sum(1 for d in diets if d < self.herb_max)
        n_carn = sum(1 for d in diets if d >= self.carn_min)
        self.rows.append(
            TickStats(
                tick=snapshot.tick,
                n_agents=n,
                n_plants=len(snapshot.plants),
                mean_energy=fmean(a.energy for a in agents),
                mean_diet=fmean(diets),
                mean_size=fmean(a.size for a in agents),
                max_generation=max(a.generation for a in agents),
                n_herb=n_herb,
                n_mid=n - n_herb - n_carn,
                n_carn=n_carn,
            )
        )

    def to_csv(self, path: str | Path) -> Path:
        """Write the accumulated rows to `path` as CSV; return the resolved Path."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        header = [f.name for f in fields(TickStats)]
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
            for row in self.rows:
                writer.writerow(asdict(row))
        return out
