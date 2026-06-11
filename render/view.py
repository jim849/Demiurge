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
    Click      select an agent (click empty space to deselect)
    Esc / Q    quit
"""

from __future__ import annotations

import os

import pygame

from core.world import World, WorldSnapshot
from render.projection import AGENT_MIN_RADIUS_PX, Camera, diet_color, pick_agent

# --- palette (render-layer constants, not simulation params) -----------------
_BG: tuple[int, int, int] = (18, 18, 22)
_FIELD_BG: tuple[int, int, int] = (28, 30, 36)
_FIELD_BORDER: tuple[int, int, int] = (70, 74, 84)
_PLANT: tuple[int, int, int] = (90, 150, 90)
_HEADING: tuple[int, int, int] = (235, 235, 235)
_TEXT: tuple[int, int, int] = (220, 220, 225)
_TEXT_DIM: tuple[int, int, int] = (150, 152, 160)
_SELECT_RING: tuple[int, int, int] = (250, 230, 120)  # highlight for the selected agent


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
        radius = camera.radius_px(agent.body_radius, minimum=AGENT_MIN_RADIUS_PX)
        pygame.draw.circle(surface, diet_color(agent.diet), center, radius)
        # A ring around whoever the user has selected (drawn under the heading line).
        if agent.id == snapshot.selected_id:
            pygame.draw.circle(surface, _SELECT_RING, center, radius + 4, width=2)
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
    panel_px: int,
    paused: bool,
    ticks_per_frame: int,
) -> None:
    """Draw the side panel: global stats, control hints, and -- when an agent is
    selected -- its chromosome read-out (the inspect view, iron law 4)."""
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
        ("click select  q quit", _TEXT_DIM),
    ]
    y = 16
    for text, color in lines:
        if text:
            surface.blit(font.render(text, True, color), (x0 + 16, y))
        y += 22

    if snapshot.selected_id is not None:
        y = _draw_selection(surface, snapshot, font, x0=x0, panel_px=panel_px, y=y + 6)


def _draw_selection(
    surface: pygame.Surface,
    snapshot: WorldSnapshot,
    font: pygame.font.Font,
    *,
    x0: int,
    panel_px: int,
    y: int,
) -> int:
    """Render the selected agent's id/energy/generation and full gene map.

    Gene values are right-aligned against the panel edge so long gene names (e.g.
    `offspring_investment`) keep their numbers lined up and readable.
    """
    selected = next((a for a in snapshot.agents if a.id == snapshot.selected_id), None)
    if selected is None:  # selection was reaped between tick and draw; nothing to show
        return y

    pygame.draw.line(surface, _FIELD_BORDER, (x0 + 12, y), (x0 + panel_px - 12, y), 1)
    y += 10
    header = [
        (f"selected #{selected.id}", _SELECT_RING),
        (f"energy {selected.energy:.1f}", _TEXT),
        (f"gen    {selected.generation}", _TEXT),
        ("genes", _TEXT_DIM),
    ]
    for text, color in header:
        surface.blit(font.render(text, True, color), (x0 + 16, y))
        y += 22

    value_right = x0 + panel_px - 16
    for name, value in (snapshot.selected_genes or {}).items():
        surface.blit(font.render(name, True, _TEXT), (x0 + 16, y))
        value_surf = font.render(f"{value:.2f}", True, _TEXT)
        surface.blit(value_surf, (value_right - value_surf.get_width(), y))
        y += 20
    return y


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
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # Click-to-select: only inside the viewport (the panel is UI, not
                    # world). Hit-test against the current snapshot and hand the core a
                    # plain id (iron law 4); a miss passes None, i.e. deselect.
                    mx, my = event.pos
                    if mx < viewport_px and my < viewport_px:
                        picked = pick_agent(world.snapshot(), camera.to_world(mx, my), camera)
                        world.select(picked)

            if not paused:
                for _ in range(speed):
                    world.tick()

            snapshot = world.snapshot()
            screen.fill(_BG)
            _draw_field(screen, snapshot, camera)
            _draw_panel(screen, snapshot, font, x0=viewport_px, panel_px=panel_px,
                        paused=paused, ticks_per_frame=speed)
            pygame.display.flip()
            clock.tick(fps)

            frames += 1
            if max_frames is not None and frames >= max_frames:
                running = False
    finally:
        pygame.quit()
