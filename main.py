"""Headless entry point: build a world from config and run the tick loop.

This is the smoke test for the simulation core (iron law 9: the core runs with no
pygame, no graphics). Its purpose is to *watch the dynamics* -- is the world alive
(not instantly extinct, not exploding) and evolving (generations advancing)? --
before any rendering layer exists. Every tunable number comes from config (iron
law 10); this file only assembles the pieces and reports.

Run:
    python main.py                  # 1000 ticks, default seed
    python main.py --ticks 5000     # longer run
    python main.py --seed 7         # a different starting world
    python main.py --every 100      # print a stats line less often
"""

from __future__ import annotations

import argparse
from statistics import fmean

import config
from core.decision.rule_based import RuleBasedBrain
from core.genome import Genome
from core.reproduction.asexual import AsexualReproduction
from core.rng import Rng
from core.world import World


def build_world(seed: int) -> World:
    """Assemble a World from config: brains, plants, predation, reproduction."""

    def brain_factory(genome: Genome) -> RuleBasedBrain:
        return RuleBasedBrain.express(genome, config.BRAIN_PARAMS)

    world = World(
        config.WORLD_SIZE,
        Rng(seed),
        schema=config.GENOME_SCHEMA,
        phenotype_params=config.PHENOTYPE_PARAMS,
        brain_factory=brain_factory,
        plant_params=config.PLANT_PARAMS,
        predation_params=config.PREDATION_PARAMS,
        reproducer=AsexualReproduction(),
        offspring_placement_factor=config.OFFSPRING_PLACEMENT_FACTOR,
    )
    world.populate(config.INITIAL_AGENT_COUNT, initial_energy=config.INITIAL_AGENT_ENERGY)
    world.scatter_plants(
        config.INITIAL_PLANT_COUNT,
        energy=config.PLANT_PARAMS.energy,
        body_radius=config.PLANT_PARAMS.body_radius,
    )
    return world


def _stats_line(world: World) -> str:
    """One line of live population stats.

    Reads live agents (not the snapshot) because generation is not part of
    AgentSnapshot -- it is a logic detail, not a rendering one.
    """
    agents = list(world.agents.values())
    n = len(agents)
    if n == 0:
        return f"tick {world.tick_count:>6} | EXTINCT"
    energy = fmean(a.energy for a in agents)
    diet = fmean(a.genome.get("diet") for a in agents)
    size = fmean(a.genome.get("size") for a in agents)
    max_gen = max(a.generation for a in agents)
    return (
        f"tick {world.tick_count:>6} | agents {n:>5} | plants {len(world.plants):>4} | "
        f"E {energy:6.1f} | diet {diet:4.2f} | size {size:4.2f} | gen {max_gen:>3}"
    )


def run(ticks: int, seed: int, every: int) -> None:
    world = build_world(seed)
    print(f"# Demiurge headless smoke run -- seed={seed}, ticks={ticks}")
    print(_stats_line(world))  # tick 0: the starting world
    for _ in range(ticks):
        world.tick()
        if world.tick_count % every == 0:
            print(_stats_line(world))
        if not world.agents:
            print(f"# population went extinct at tick {world.tick_count}")
            break
    else:
        print("# run complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Demiurge headless simulation run.")
    parser.add_argument("--ticks", type=int, default=1000, help="number of ticks to run")
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED, help="world seed")
    parser.add_argument("--every", type=int, default=50, help="print a stats line every N ticks")
    args = parser.parse_args()
    run(ticks=args.ticks, seed=args.seed, every=args.every)


if __name__ == "__main__":
    main()
