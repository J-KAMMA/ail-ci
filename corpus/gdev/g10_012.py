# task: Write a script that runs Dijkstra's algorithm with heapq on a hardcoded weighted directed graph and prints the distance from a source to every node.
import heapq
from typing import Dict, List, Tuple


Graph = Dict[str, List[Tuple[str, int]]]


def build_graph() -> Graph:
    """Return a hardcoded weighted directed graph as an adjacency list."""
    return {
        "A": [("B", 7), ("C", 9), ("F", 14)],
        "B": [("A", 7), ("C", 10), ("D", 15)],
        "C": [("A", 9), ("B", 10), ("D", 11), ("F", 2)],
        "D": [("B", 15), ("C", 11), ("E", 6)],
        "E": [("D", 6), ("F", 9)],
        "F": [("A", 14), ("C", 2), ("E", 9)],
        "G": [("A", 3)],
    }


def dijkstra(graph: Graph, source: str) -> Dict[str, float]:
    """Compute shortest distances from source to every node using a heap."""
    nodes = set(graph)
    for edges in graph.values():
        for target, _ in edges:
            nodes.add(target)

    dist: Dict[str, float] = {node: float("inf") for node in nodes}
    dist[source] = 0
    heap: List[Tuple[int, str]] = [(0, source)]

    while heap:
        d, node = heapq.heappop(heap)
        if d > dist[node]:
            continue  # stale entry
        for neighbor, weight in graph.get(node, []):
            candidate = d + weight
            if candidate < dist[neighbor]:
                dist[neighbor] = candidate
                heapq.heappush(heap, (candidate, neighbor))

    return dist


def main() -> None:
    graph = build_graph()
    source = "A"
    distances = dijkstra(graph, source)

    print(f"Shortest distances from source {source}:")
    for node in sorted(distances):
        d = distances[node]
        if d == float("inf"):
            print(f"  {node}: unreachable")
        else:
            print(f"  {node}: {int(d)}")


if __name__ == "__main__":
    main()
