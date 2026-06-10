"""The pygame view: window, event loop, and drawing.

The thin shell around the pure helpers in `render/projection.py`. It pulls a
`WorldSnapshot` from the core each frame and draws it; it never reaches into live
agents (iron law 2). Simulation stepping and frame rate are decoupled: the screen
refreshes at a fixed FPS while `ticks_per_frame` advances the simulation -- so a
human can watch a fast world by slowing the *display*, not the model.

Controls:
    Space      pause / resume
    . (period) single-step one tick (while paused)
    Up / Down  faster / slower (ticks per frame)
    Esc / Q    quit
"""

from __future__ import annotations

import os

import pygame

from core.world import World, WorldSnapshot
from render.projection import Camera, diet_color

# --- palette (render-layer constants, not simulation params) -----------------
_BG: tuple[int, int, int] = (18, 18, 22)
_FIELD_BG: tuple[int, int, int] = (28, 30, 36)
_FIELD_BORDER: tuple[int, int, int] = (70, 74, 84)
_PLANT: tuple[int, int, int] = (90, 150, 90)
_HEADING: tuple[int, int, int] = (235, 235, 235)
_TEXT: tuple[int, int, int] = (220, 220, 225)
_TEXT_DIM: tuple[int, int, int] = (150, 152, 160)


def _draw_field(surface: pygame.Surface, snapshot: WorldSnapshot, camera: Camera) -> None:
    """Draw the world: bounds, plants, then agents (agents on top)."""
    extent = camera.viewport_px
    surface.fill(_FIELD_BG, pygame.Rect(0, 0, extent, extent))
    pygame.draw.rect(surface, _FIELD_BORDER, pygame.Rect(0, 0, extent, extent), width=1)

    for plant in snapshot.plants:
        pygame.draw.circle(surface, _PLANT, camera.to_screen(plant.position),
                           camera.radius_px(plant.body_radius, minimum=2))

    for agent in snapshot.agents:
        center = camera.to_screen(agent.position)
        radius = camera.radius_px(agent.body_radius, minimum=2)
        pygame.draw.circle(surface, diet_color(agent.diet), center, radius)
        # A short line showing which way it faces (only when big enough to see).
        if radius >= 3:
            heading = agent.heading.normalized()
            tip = (round(center[0] + heading.x * radius), round(center[1] + heading.y * radius))
            pygame.draw.line(surface, _HEADING, center, tip, 1)


def _draw_panel(
    surface: pygame.Surface,
    snapshot: WorldSnapshot,
    font: pygame.font.Font,
    *,
    x0: int,
    paused: bool,
    ticks_per_frame: int,
) -> None:
    """Draw the side panel: global stats from the snapshot + control hints."""
    agents = snapshot.agents
    n = len(agents)
    if n:
        mean_diet = sum(a.diet for a in agents) / n
        mean_size = sum(a.size for a in agents) / n
        mean_energy = sum(a.energy for a in agents) / n
    else:
        mean_diet = mean_size = mean_energy = 0.0

    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"tick   {snapshot.tick}", _TEXT),
        (f"agents {n}", _TEXT),
        (f"plants {len(snapshot.plants)}", _TEXT),
        ("", _TEXT),
        (f"mean diet   {mean_diet:.2f}", _TEXT),
        (f"mean size   {mean_size:.2f}", _TEXT),
        (f"mean energy {mean_energy:.1f}", _TEXT),
        ("", _TEXT),
        ("PAUSED" if paused else f"speed  {ticks_per_frame}x", _TEXT_DIM),
        ("", _TEXT),
        ("space pause   . step", _TEXT_DIM),
        ("up/down speed  q quit", _TEXT_DIM),
    ]
    y = 16
    for text, color in lines:
        if text:
            surface.blit(font.render(text, True, color), (x0 + 16, y))
        y += 22


def run(
    world: World,
    *,
    viewport_px: int = 800,
    panel_px: int = 240,
    fps: int = 60,
    ticks_per_frame: int = 1,
    max_frames: int | None = None,
) -> None:
    """Open a window and run the render/sim loop until the user quits.

    `max_frames` (test/smoke only) stops after that many frames instead of waiting
    for a quit event, so the loop can run headless under SDL's dummy video driver.
    """
    pygame.init()
    try:
        camera = Camera(world.size, viewport_px)  # raises early if world isn't 2D
        screen = pygame.display.set_mode((viewport_px + panel_px, viewport_px))
        pygame.display.set_caption("Demiurge")
        font = pygame.font.SysFont("menlo,monospace", 16)
        clock = pygame.time.Clock()

        paused = False
        speed = max(1, ticks_per_frame)
        frames = 0
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_PERIOD and paused:
                        world.tick()
                    elif event.key == pygame.K_UP:
                        speed = min(speed + 1, 100)
                    elif event.key == pygame.K_DOWN:
                        speed = max(speed - 1, 1)

            if not paused:
                for _ in range(speed):
                    world.tick()

            snapshot = world.snapshot()
            screen.fill(_BG)
            _draw_field(screen, snapshot, camera)
            _draw_panel(screen, snapshot, font, x0=viewport_px, paused=paused, ticks_per_frame=speed)
            pygame.display.flip()
            clock.tick(fps)

            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False
    finally:
        pygame.quit()
