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
from core.vector import Vector
from core.world import World, random_unit_vector
from demiurge.interventions import Demiurge


def build_world(seed: int, *, seed_plan: dict[str, int] | None = None) -> World:
    """Assemble a World from config: brains, plants, predation, reproduction.

    With `seed_plan` (morph name -> count), the world is filled with coherent,
    hand-designed morphs (config.MORPHS) via the creator channel instead of a
    random population -- a clean, known starting composition for predator-prey
    balance experiments. Without it, the default random `populate` runs.
    """

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
        spatial_cell_size=config.SPATIAL_CELL_SIZE,
    )
    if seed_plan is None:
        world.populate(config.INITIAL_AGENT_COUNT, initial_energy=config.INITIAL_AGENT_ENERGY)
    else:
        _seed_morphs(world, seed, seed_plan)
    world.scatter_plants(
        config.INITIAL_PLANT_COUNT,
        energy=config.PLANT_PARAMS.energy,
        body_radius=config.PLANT_PARAMS.body_radius,
    )
    return world


def _seed_morphs(world: World, seed: int, seed_plan: dict[str, int]) -> None:
    """Place `count` of each named morph at deterministic-random positions.

    Experiment-harness glue (not core): the creator channel only knows how to make
    one agent at an explicit position, so this loop owns the random placement +
    facing. Its own seeded sub-stream keeps the layout reproducible and independent
    of the world's internal draws.
    """
    demiurge = Demiurge(world, config.GENOME_SCHEMA)
    place_rng = Rng(seed).spawn("seeding")
    dim = world.size.dim
    for morph_name, count in seed_plan.items():
        genes = config.MORPHS[morph_name]
        for _ in range(count):
            position = Vector.from_iterable(place_rng.uniform(0.0, extent) for extent in world.size)
            heading = random_unit_vector(dim, place_rng)
            demiurge.create_agent(
                genes, position, heading=heading, energy=config.INITIAL_AGENT_ENERGY
            )


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


def _resolve_seed_plan(args: argparse.Namespace) -> dict[str, int] | None:
    """Turn the seeding CLI flags into a plan, or None for random populate.

    Seeding is on if `--seed-morph` is given OR any count override is. The plan
    starts from config.SEED_PLAN and applies --herb/--carn overrides on top, so a
    balance sweep can vary the ratio without editing config.
    """
    if not (args.seed_morph or args.herb is not None or args.carn is not None):
        return None
    plan = dict(config.SEED_PLAN)
    if args.herb is not None:
        plan["herb"] = args.herb
    if args.carn is not None:
        plan["carn"] = args.carn
    return plan


def run(ticks: int, seed: int, every: int, seed_plan: dict[str, int] | None = None) -> None:
    world = build_world(seed, seed_plan=seed_plan)
    composition = "random" if seed_plan is None else ", ".join(f"{n}x{m}" for m, n in seed_plan.items())
    print(f"# Demiurge headless smoke run -- seed={seed}, ticks={ticks}, pop={composition}")
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
    parser = argparse.ArgumentParser(description="Demiurge simulation run.")
    parser.add_argument("--ticks", type=int, default=1000, help="number of ticks to run (headless)")
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED, help="world seed")
    parser.add_argument("--every", type=int, default=50, help="print a stats line every N ticks (headless)")
    parser.add_argument("--render", action="store_true", help="open a pygame window instead of running headless")
    parser.add_argument("--seed-morph", action="store_true",
                        help="seed coherent morphs (config.SEED_PLAN) instead of a random population")
    parser.add_argument("--herb", type=int, default=None, help="override herbivore seed count (implies --seed-morph)")
    parser.add_argument("--carn", type=int, default=None, help="override carnivore seed count (implies --seed-morph)")
    args = parser.parse_args()

    seed_plan = _resolve_seed_plan(args)

    if args.render:
        # Lazy import so the headless path stays free of any pygame dependency
        # (iron law 1): pygame is only touched when a window is actually requested.
        from render.view import run as run_render

        run_render(build_world(args.seed, seed_plan=seed_plan))
    else:
        run(ticks=args.ticks, seed=args.seed, every=args.every, seed_plan=seed_plan)


if __name__ == "__main__":
    main()
