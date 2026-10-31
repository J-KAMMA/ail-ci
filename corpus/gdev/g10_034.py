# task: Write a script that computes the shortest path in a hardcoded graph where edge weights are only 0 or 1 using a deque-based 0-1 BFS and prints the distance.
from collections import deque
from typing import Dict, List, Tuple


def build_graph() -> Dict[str, List[Tuple[str, int]]]:
    """Return a hardcoded directed graph with edge weights of 0 or 1."""
    edges: List[Tuple[str, str, int]] = [
        ("A", "B", 0),
        ("A", "C", 1),
        ("B", "C", 0),
        ("B", "D", 1),
        ("C", "D", 0),
        ("C", "E", 1),
        ("D", "E", 0),
        ("D", "F", 1),
        ("E", "F", 0),
        ("E", "G", 1),
        ("F", "G", 1),
        ("G", "H", 0),
        ("F", "H", 1),
    ]
    graph: Dict[str, List[Tuple[str, int]]] = {}
    for u, v, w in edges:
        graph.setdefault(u, []).append((v, w))
        graph.setdefault(v, [])
    return graph


def zero_one_bfs(graph: Dict[str, List[Tuple[str, int]]], source: str) -> Dict[str, int]:
    """Compute shortest distances from source using a deque-based 0-1 BFS."""
    INF = float("inf")
    dist: Dict[str, float] = {node: INF for node in graph}
    dist[source] = 0
    dq: deque[str] = deque([source])

    while dq:
        node = dq.popleft()
        d = dist[node]
        for neighbor, weight in graph[node]:
            nd = d + weight
            if nd < dist[neighbor]:
                dist[neighbor] = nd
                if weight == 0:
                    dq.appendleft(neighbor)
                else:
                    dq.append(neighbor)

    return {node: int(d) for node, d in dist.items()}


def main() -> None:
    graph = build_graph()
    source = "A"
    target = "H"

    distances = zero_one_bfs(graph, source)
    print(f"Shortest distance from {source} to {target}: {distances[target]}")


if __name__ == "__main__":
    main()
