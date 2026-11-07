"""Conway's Game of Life on a torus, using a set of live cells."""
import sys

SMALL = "--small" in sys.argv
SIZE = 24 if SMALL else 190
GENERATIONS = 20 if SMALL else 150

seed = 8675309


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


live = set()
for x in range(SIZE):
    for y in range(SIZE):
        if rnd() % 100 < 31:
            live.add((x, y))


def step(cells, size):
    neighbours = {}
    for x, y in sorted(cells):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                point = ((x + dx) % size, (y + dy) % size)
                neighbours[point] = neighbours.get(point, 0) + 1
    result = set()
    for point, count in neighbours.items():
        if count == 3 or (count == 2 and point in cells):
            result.add(point)
    return result


initial = len(live)
for _ in range(GENERATIONS):
    live = step(live, SIZE)

checksum = 0
for x, y in sorted(live):
    checksum += (x + 1) * (y + 1)

print("size", SIZE)
print("generations", GENERATIONS)
print("initial", initial)
print("final", len(live))
print("checksum", checksum)
