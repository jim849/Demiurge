"""Agent: one individual organism in the world.

Design decisions (see PLAN.md, Milestone 0/1):
- **Lean agent, not a rich domain object.** An Agent is mostly a state container
  (genome + expressed phenotype + position/energy/age). The *policies* that act on
  it -- how it decides, how it moves, how it reproduces -- live in replaceable
  external modules (`decision/`, `reproduction/`, and the resolve phase of
  `world.py`), per iron law 5. The Agent never imports those modules, so it stays
  trivially testable headless (iron law 9) and decision/reproduction stay
  swappable without touching this class.
- **A few state-integrity methods only.** The exception to "pure data" is a small
  set of methods that guard the agent's own invariants (energy never goes
  negative; re-expressing the phenotype after a gene edit; marking death). These
  are NOT policies -- they protect internal consistency so external code can't
  forget to, e.g., clamp energy.
- **Genotype vs phenotype.** `genome` is the mutable, heritable, editable code.
  `phenotype` is the immutable abilities expressed from it (computed once at
  birth, cached). If the genome changes (a creator edit, or future in-life
  radiation), call `re_express(params)` to rebuild the frozen phenotype.
- **id is assigned by the World**, not generated here: the World owns a stable,
  deterministic counter (iron law 7). The Agent simply receives its id.
- **age / generation are stored now, inert in v1.** No lifespan cap yet (death is
  energy<=0 or predation), but `age` feeds future senescence/ontogeny (M6) and
  `generation` feeds lineage-depth analysis (M4); both are cheap ints/lost forever
  if not recorded, so they are kept from day one.
"""

from __future__ import annotations

from core.genome import Genome
from core.phenotype import Phenotype, PhenotypeParams, express
from core.vector import Vector


class Agent:
    """One individual: heritable genome + expressed phenotype + mutable life state."""

    __slots__ = (
        "id",
        "genome",
        "phenotype",
        "position",
        "heading",
        "energy",
        "age",
        "generation",
        "alive",
    )

    def __init__(
        self,
        agent_id: int,
        genome: Genome,
        phenotype: Phenotype,
        position: Vector,
        *,
        heading: Vector | None = None,
        energy: float = 0.0,
        generation: int = 0,
    ) -> None:
        if energy < 0:
            raise ValueError("energy cannot be negative")
        if generation < 0:
            raise ValueError("generation cannot be negative")

        self.id = agent_id
        self.genome = genome
        self.phenotype = phenotype
        self.position = position
        # No facing yet in v1 -> default to the zero vector of matching dimension.
        # (Movement is size-neutral in v1; heading is stored for rendering and the
        # future inertia model in M5.)
        self.heading = heading if heading is not None else Vector.zero(position.dim)
        self.energy = float(energy)
        self.age = 0
        self.generation = generation
        self.alive = True

    # --- state-integrity methods (not policies) -------------------------------

    def add_energy(self, amount: float) -> None:
        """Gain energy (e.g. from eating). `amount` must be non-negative."""
        if amount < 0:
            raise ValueError("add_energy expects a non-negative amount")
        self.energy += amount

    def spend_energy(self, amount: float) -> None:
        """Spend energy (movement/resting cost), clamped so it never goes negative.

        Clamping here means external systems can subtract costs without each
        remembering to guard the floor. Whether the agent then *dies* (energy
        hit 0) is decided by the world's resolve phase, not here.
        """
        if amount < 0:
            raise ValueError("spend_energy expects a non-negative amount")
        self.energy = max(0.0, self.energy - amount)

    def advance_age(self) -> None:
        """Increment age by one tick. Inert in v1; used by M6 life-history."""
        self.age += 1

    def re_express(self, params: PhenotypeParams) -> None:
        """Rebuild the (immutable) phenotype from the current genome.

        Call after a gene edit (creator intervention) or future in-life mutation.
        The phenotype stays a frozen value object; we replace it wholesale rather
        than mutate it.
        """
        self.phenotype = express(self.genome, params)

    def mark_dead(self) -> None:
        """Flag this agent as dead. The world removes dead agents in resolve."""
        self.alive = False

    # --- representation -------------------------------------------------------

    def __repr__(self) -> str:
        state = "alive" if self.alive else "dead"
        return (
            f"Agent(id={self.id}, gen={self.generation}, "
            f"energy={self.energy:.2f}, age={self.age}, {state})"
        )
