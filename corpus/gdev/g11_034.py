# task: Simulate a Wa-Tor-like predator-prey model on a 10x10 toroidal grid with fixed seed for 20 steps and print the final counts of fish and sharks.
from __future__ import annotations

import random
from dataclasses import dataclass

SIZE = 10
STEPS = 20
SEED = 42

INITIAL_FISH = 20
INITIAL_SHARKS = 5

FISH_BREED_AGE = 3
SHARK_BREED_AGE = 8
SHARK_START_ENERGY = 5
SHARK_ENERGY_PER_FISH = 3


@dataclass
class Creature:
    is_shark: bool
    age: int = 0
    energy: int = 0


Grid = list[list[Creature | None]]
Pos = tuple[int, int]


def new_grid() -> Grid:
    return [[None for _ in range(SIZE)] for _ in range(SIZE)]


def get(grid: Grid, pos: Pos) -> Creature | None:
    r, c = pos
    return grid[r][c]


def set_cell(grid: Grid, pos: Pos, creature: Creature | None) -> None:
    r, c = pos
    grid[r][c] = creature


def neighbors(pos: Pos) -> list[Pos]:
    r, c = pos
    return [
        ((r - 1) % SIZE, c),
        ((r + 1) % SIZE, c),
        (r, (c - 1) % SIZE),
        (r, (c + 1) % SIZE),
    ]


def populate(grid: Grid, rng: random.Random) -> None:
    all_cells: list[Pos] = [(r, c) for r in range(SIZE) for c in range(SIZE)]
    chosen = rng.sample(all_cells, INITIAL_FISH + INITIAL_SHARKS)
    for index, pos in enumerate(chosen):
        if index < INITIAL_FISH:
            set_cell(grid, pos, Creature(is_shark=False))
        else:
            set_cell(grid, pos, Creature(is_shark=True, energy=SHARK_START_ENERGY))


def step(grid: Grid, rng: random.Random) -> None:
    order: list[Pos] = [(r, c) for r in range(SIZE) for c in range(SIZE)]
    rng.shuffle(order)
    processed: set[Pos] = set()

    for pos in order:
        if pos in processed:
            continue
        creature = get(grid, pos)
        if creature is None:
            continue

        processed.add(pos)
        creature.age += 1

        if creature.is_shark:
            creature.energy -= 1
            if creature.energy <= 0:
                set_cell(grid, pos, None)
                continue

        nbrs = neighbors(pos)
        destination: Pos | None = None
        ate_fish = False

        if creature.is_shark:
            prey = [p for p in nbrs if (n := get(grid, p)) is not None and not n.is_shark]
            if prey:
                destination = rng.choice(prey)
                ate_fish = True
        if destination is None:
            empty = [p for p in nbrs if get(grid, p) is None]
            if empty:
                destination = rng.choice(empty)

        if destination is None:
            continue

        if ate_fish:
            creature.energy += SHARK_ENERGY_PER_FISH

        breed_age = SHARK_BREED_AGE if creature.is_shark else FISH_BREED_AGE
        left_behind: Creature | None = None
        if creature.age >= breed_age:
            creature.age = 0
            left_behind = Creature(
                is_shark=creature.is_shark,
                age=0,
                energy=SHARK_START_ENERGY if creature.is_shark else 0,
            )

        set_cell(grid, pos, left_behind)
        set_cell(grid, destination, creature)
        processed.add(destination)


def count(grid: Grid) -> tuple[int, int]:
    fish = 0
    sharks = 0
    for row in grid:
        for cell in row:
            if cell is None:
                continue
            if cell.is_shark:
                sharks += 1
            else:
                fish += 1
    return fish, sharks


def main() -> None:
    rng = random.Random(SEED)
    grid = new_grid()
    populate(grid, rng)

    for _ in range(STEPS):
        step(grid, rng)

    fish, sharks = count(grid)
    print(f"After {STEPS} steps on a {SIZE}x{SIZE} torus:")
    print(f"Fish: {fish}")
    print(f"Sharks: {sharks}")


if __name__ == "__main__":
    main()
