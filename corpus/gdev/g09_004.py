# task: Solve a 0/1 knapsack problem with a hardcoded list of item weights and values and capacity 50, then print the maximum value.
from typing import Sequence


def knapsack_max_value(weights: Sequence[int], values: Sequence[int], capacity: int) -> int:
    """Return the maximum total value achievable with total weight <= capacity (0/1 knapsack)."""
    best: list[int] = [0] * (capacity + 1)
    for weight, value in zip(weights, values):
        # Iterate capacities downward so each item is used at most once.
        for cap in range(capacity, weight - 1, -1):
            candidate = best[cap - weight] + value
            if candidate > best[cap]:
                best[cap] = candidate
    return best[capacity]


def main() -> None:
    weights: list[int] = [10, 20, 30, 15, 25, 5, 12, 8]
    values: list[int] = [60, 100, 120, 75, 110, 30, 70, 45]
    capacity: int = 50

    max_value: int = knapsack_max_value(weights, values, capacity)
    print(f"Maximum value with capacity {capacity}: {max_value}")


if __name__ == "__main__":
    main()
