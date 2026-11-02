# task: Write a script that computes the diameter of a hardcoded unweighted tree by running BFS twice and prints the result.
from collections import deque


def bfs(adj: dict[int, list[int]], start: int) -> tuple[int, dict[int, int]]:
    """Return the farthest node from start and the distance map from start."""
    dist: dict[int, int] = {start: 0}
    queue: deque[int] = deque([start])
    farthest = start
    while queue:
        node = queue.popleft()
        if dist[node] > dist[farthest]:
            farthest = node
        for neighbor in adj[node]:
            if neighbor not in dist:
                dist[neighbor] = dist[node] + 1
                queue.append(neighbor)
    return farthest, dist


def build_tree() -> dict[int, list[int]]:
    """Hardcoded unweighted tree as an adjacency list."""
    edges: list[tuple[int, int]] = [
        (0, 1),
        (1, 2),
        (1, 3),
        (3, 4),
        (4, 5),
        (4, 6),
        (6, 7),
        (7, 8),
        (2, 9),
        (9, 10),
    ]
    adj: dict[int, list[int]] = {}
    for u, v in edges:
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)
    return adj


def main() -> None:
    adj = build_tree()
    start = min(adj)
    endpoint_a, _ = bfs(adj, start)
    endpoint_b, dist = bfs(adj, endpoint_a)
    diameter = dist[endpoint_b]
    print(f"Diameter: {diameter}")


if __name__ == "__main__":
    main()
