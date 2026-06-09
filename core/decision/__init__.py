"""Replaceable decision (brain) module (iron law 5).

A decision-maker is a pure function `perception -> action`. The interface lives
in `base.py`; concrete brains (rule-based in v1, neural network in M2) implement
it without the core engine changing. This package never imports pygame or config.
"""
