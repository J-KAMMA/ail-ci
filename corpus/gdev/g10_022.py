# task: Write a script that computes the minimum spanning tree of a hardcoded weighted graph using Prim's algorithm with heapq and prints the total weight.
import heapq
from typing import Dict, List, Set, Tuple

Edge = Tuple[str, str, int]
Graph = Dict[str, List[Tuple[str, int]]]


def build_graph(edges: List[Edge]) -> Graph:
    """Build an undirected adjacency list, preserving insertion order."""
    graph: Graph = {}
    for u, v, w in edges:
        graph.setdefault(u, []).append((v, w))
        graph.setdefault(v, []).append((u, w))
    return graph


def prim_mst(graph: Graph, start: str) -> Tuple[int, List[Edge]]:
    """
    Compute a minimum spanning tree with Prim's algorithm using heapq.
    Returns the total weight and the list of tree edges.
    Raises ValueError if the graph is disconnected.
    """
    if not graph:
        return 0, []

    visited: Set[str] = {start}
    tree: List[Edge] = []
    total_weight = 0

    # Heap entries: (weight, from_node, to_node). Tuples of ints and strings
    # compare deterministically, so ties are resolved the same way every run.
    heap: List[Tuple[int, str, str]] = []
    for neighbor, weight in graph[start]:
        heapq.heappush(heap, (weight, start, neighbor))

    while heap and len(visited) < len(graph):
        weight, u, v = heapq.heappop(heap)
        if v in visited:
            continue

        visited.add(v)
        total_weight += weight
        tree.append((u, v, weight))

        for neighbor, w in graph[v]:
            if neighbor not in visited:
                heapq.heappush(heap, (w, v, neighbor))

    if len(visited) != len(graph):
        raise ValueError("graph is disconnected; no spanning tree exists")

    return total_weight, tree


def main() -> None:
    edges: List[Edge] = [
        ("A", "B", 7),
        ("A", "D", 5),
        ("B", "C", 8),
        ("B", "D", 9),
        ("B", "E", 7),
        ("C", "E", 5),
        ("D", "E", 15),
        ("D", "F", 6),
        ("E", "F", 8),
        ("E", "G", 9),
        ("F", "G", 11),
    ]

    graph = build_graph(edges)
    start = min(graph)  # deterministic starting vertex
    total_weight, tree = prim_mst(graph, start)

    print(f"Total MST weight: {total_weight}")


if __name__ == "__main__":
    main()
