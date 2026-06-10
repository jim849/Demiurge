"""Pure, pygame-free projection + colour helpers for the render layer.

Kept separate from the pygame shell (`render/view.py`) so the math -- mapping
world coordinates to screen pixels, colouring an agent by its diet, sizing a body
in pixels -- is unit-testable headless. Nothing here imports pygame.

The renderer is necessarily 2D (a screen has two axes), even though the core is
dimension-agnostic; `Camera` therefore requires a 2D world and says so loudly.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.vector import Vector

RGB = tuple[int, int, int]

# Colour endpoints for the diet axis (kept here, a render concern, not in config).
_HERBIVORE: RGB = (60, 200, 70)   # diet = 0: green
_CARNIVORE: RGB = (210, 60, 60)   # diet = 1: red


def diet_color(diet: float) -> RGB:
    """Map diet in [0, 1] to a colour: herbivore (0) green -> carnivore (1) red.

    Linear interpolation between the two endpoints; values outside [0, 1] clamp.
    """
    d = 0.0 if diet < 0.0 else 1.0 if diet > 1.0 else diet
    return tuple(  # type: ignore[return-value]
        round(lo + (hi - lo) * d) for lo, hi in zip(_HERBIVORE, _CARNIVORE)
    )


@dataclass(frozen=True)
class Camera:
    """Maps world coordinates (world units) to screen pixels for a 2D view.

    Uniform fit: the larger world extent fills `viewport_px`, so a square world
    fills a square viewport with no distortion. The viewport's origin is the
    top-left pixel (0, 0), matching pygame's surface coordinates.
    """

    world_size: Vector
    viewport_px: int

    def __post_init__(self) -> None:
        if self.world_size.dim != 2:
            raise ValueError("the renderer is 2D; world must be 2-dimensional")
        if self.viewport_px <= 0:
            raise ValueError("viewport_px must be positive")

    @property
    def scale(self) -> float:
        """Pixels per world unit (uniform on both axes)."""
        return self.viewport_px / max(self.world_size.x, self.world_size.y)

    def to_screen(self, world_pos: Vector) -> tuple[int, int]:
        """World position -> integer (x, y) pixel on the viewport."""
        s = self.scale
        return (round(world_pos.x * s), round(world_pos.y * s))

    def to_world(self, screen_x: float, screen_y: float) -> Vector:
        """Viewport pixel -> world position (the inverse of `to_screen`).

        Used by click-to-select in a later step; defined here so the mapping and
        its inverse live together and stay consistent.
        """
        s = self.scale
        return Vector(screen_x / s, screen_y / s)

    def radius_px(self, world_radius: float, *, minimum: int = 1) -> int:
        """A body radius (world units) in pixels, never smaller than `minimum` so
        tiny agents stay visible (and, later, clickable)."""
        return max(minimum, round(world_radius * self.scale))
