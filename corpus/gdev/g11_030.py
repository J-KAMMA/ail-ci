# task: Compute the number of paths of exactly k steps from a start cell to an end cell on an unbounded 2D lattice using dynamic programming and print the count for k=12.
from collections import defaultdict

# Four-neighbour moves on the unbounded integer lattice Z^2.
MOVES: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

START: tuple[int, int] = (0, 0)
END: tuple[int, int] = (2, 2)
K: int = 12


def count_paths(start: tuple[int, int], end: tuple[int, int], steps: int) -> int:
    """Return the number of walks of exactly `steps` unit moves from start to end."""
    current: dict[tuple[int, int], int] = {start: 1}
    for _ in range(steps):
        nxt: defaultdict[tuple[int, int], int] = defaultdict(int)
        for (x, y), ways in current.items():
            for dx, dy in MOVES:
                nxt[(x + dx, y + dy)] += ways
        current = dict(nxt)
    return current.get(end, 0)


def main() -> None:
    result = count_paths(START, END, K)
    print(f"Number of {K}-step paths from {START} to {END}: {result}")


if __name__ == "__main__":
    main()
