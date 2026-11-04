# task: Solve a five-city traveling salesman instance with bitmask dynamic programming and print the minimum tour cost.
from typing import List


def solve_tsp(dist: List[List[int]]) -> int:
    """Return the minimum cost of a Hamiltonian cycle using bitmask DP (Held-Karp)."""
    n = len(dist)
    if n <= 1:
        return 0
    full = 1 << n
    inf = float("inf")
    # dp[mask][j]: min cost to start at city 0, visit exactly the cities in mask, end at j
    dp: List[List[float]] = [[inf] * n for _ in range(full)]
    dp[1][0] = 0
    for mask in range(full):
        if not (mask & 1):
            continue
        for last in range(n):
            cost = dp[mask][last]
            if cost == inf or not (mask >> last) & 1:
                continue
            for nxt in range(n):
                if (mask >> nxt) & 1:
                    continue
                new_mask = mask | (1 << nxt)
                new_cost = cost + dist[last][nxt]
                if new_cost < dp[new_mask][nxt]:
                    dp[new_mask][nxt] = new_cost
    all_mask = full - 1
    best = inf
    for last in range(n):
        if dp[all_mask][last] == inf:
            continue
        total = dp[all_mask][last] + dist[last][0]
        if total < best:
            best = total
    return int(best)


def main() -> None:
    cities = ["A", "B", "C", "D", "E"]
    dist: List[List[int]] = [
        [0, 2, 9, 10, 7],
        [1, 0, 6, 4, 3],
        [15, 7, 0, 8, 5],
        [6, 3, 12, 0, 9],
        [10, 4, 8, 11, 0],
    ]
    cost = solve_tsp(dist)
    print(f"Cities: {', '.join(cities)}")
    print(f"Minimum tour cost: {cost}")


if __name__ == "__main__":
    main()
