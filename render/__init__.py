"""Rendering / input layer (pygame).

This package is the ONLY place pygame is allowed (iron law 1: the simulation core
imports zero pygame). It consumes pure-data `WorldSnapshot`s from the core and
never touches live `Agent`/`Plant` objects (iron law 2).

Split into:
- `projection`  -- pure, pygame-free math (world<->screen, diet colour, picking),
                   so the mapping logic is unit-testable headless;
- `view`        -- the thin pygame shell (window, event loop, drawing).
"""
