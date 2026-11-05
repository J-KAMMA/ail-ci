"""0/1 knapsack dynamic programming: best value and the chosen items."""
import sys

SMALL = "--small" in sys.argv
ITEMS = 32 if SMALL else 700
CAPACITY = 180 if SMALL else 7000

seed = 909090


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


weights = []
values = []
for _ in range(ITEMS):
    weights.append(1 + rnd() % 70)
    values.append(1 + rnd() % 100)

table = [[0] * (CAPACITY + 1) for _ in range(ITEMS + 1)]
for i in range(1, ITEMS + 1):
    weight = weights[i - 1]
    value = values[i - 1]
    previous = table[i - 1]
    row = table[i]
    for capacity in range(CAPACITY + 1):
        best = previous[capacity]
        if weight <= capacity:
            with_item = previous[capacity - weight] + value
            if with_item > best:
                best = with_item
        row[capacity] = best

chosen = []
capacity = CAPACITY
for i in range(ITEMS, 0, -1):
    if table[i][capacity] != table[i - 1][capacity]:
        chosen.append(i - 1)
        capacity -= weights[i - 1]
chosen.reverse()

total_weight = 0
for index in chosen:
    total_weight += weights[index]

print("items", ITEMS)
print("capacity", CAPACITY)
print("best", table[ITEMS][CAPACITY])
print("chosen", len(chosen))
print("weight", total_weight)
print("indices", chosen[:12])
