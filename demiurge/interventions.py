"""Demiurge: the creator's three intervention capabilities.

This is the programmatic layer the M0 design specified (PLAN.md, Milestone 0,
"Gene system layering"): the low-level, range-validated gene read/write lives in
`core/genome.py` (no world knowledge); this module is the thin caller on top that
adds *world placement* and exposes the three creator-facing capabilities:

    1. read_genes   -- read any living agent's genes
    2. edit_gene    -- edit a gene on any living agent (then re-express it)
    3. create_agent -- build a brand-new agent from explicit gene values and place
                       it into the world at a chosen position

A future graphical gene editor is meant to be a thin layer over this same API, so
everything here stays pure logic (no pygame, iron laws 1/9) and is testable
headless. The Demiurge holds only a `world` reference and the genome `schema`; it
reaches the phenotype params and brain factory *through* the World (via
`spawn_agent` and `re_express_agent`) so expression has a single source of truth.
"""

from __future__ import annotations

from core.agent import Agent
from core.genome import ChromosomeSpec, Genome
from core.vector import Vector
from core.world import World


class Demiurge:
    """The creator's hands: read/edit genes and create agents in a live world."""

    __slots__ = ("_world", "_schema")

    def __init__(self, world: World, schema: tuple[ChromosomeSpec, ...]) -> None:
        self._world = world
        self._schema = schema

    # --- capability 1: read ---------------------------------------------------

    def read_genes(self, agent_id: int) -> dict[str, float]:
        """Return a flat {gene_name: value} snapshot of a living agent's genome."""
        return self._agent(agent_id).genome.as_dict()

    # --- capability 2: edit ---------------------------------------------------

    def edit_gene(self, agent_id: int, gene_name: str, value: float) -> None:
        """Set one gene on a living agent, then re-express its phenotype + brain.

        The write is range-validated by the genome (raises if out of range or the
        gene name is unknown). Because the phenotype and brain are expressed once
        at birth and cached, the edit only takes effect after re-expression -- so
        we always re-express, keeping the agent's abilities consistent with its
        (now-changed) genes.
        """
        agent = self._agent(agent_id)
        agent.genome.set(gene_name, value)
        self._world.re_express_agent(agent)

    # --- capability 3: create -------------------------------------------------

    def create_agent(
        self,
        gene_values: dict[str, float],
        position: Vector,
        *,
        energy: float = 0.0,
        heading: Vector | None = None,
        generation: int = 0,
    ) -> Agent:
        """Build a new agent from explicit gene values and place it in the world.

        Every schema gene must be supplied (no implicit defaults) and no extras --
        `Genome.from_values` enforces this. The World assigns the id, expresses the
        phenotype + brain, and wraps the position into the torus.
        """
        genome = Genome.from_values(self._schema, gene_values)
        return self._world.spawn_agent(
            genome,
            position,
            heading=heading,
            energy=energy,
            generation=generation,
        )

    # --- internals ------------------------------------------------------------

    def _agent(self, agent_id: int) -> Agent:
        """Resolve an agent id to a living Agent, with a clear error if absent."""
        agent = self._world.agents.get(agent_id)
        if agent is None:
            raise KeyError(f"no agent with id {agent_id} in the world")
        return agent
