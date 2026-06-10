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

from abc import ABC, abstractmethod
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
