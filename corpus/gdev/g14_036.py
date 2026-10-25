# task: Create a dataclass Graph edge list representation and perform a breadth-first search returning the visit order.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Graph:
    """A graph stored as an ordered edge list.

    Vertices are strings. If `directed` is False, every edge (u, v)
    also allows travel from v to u.
    """

    edges: tuple[tuple[str, str], ...]
    directed: bool = False

    def vertices(self) -> list[str]:
        """Return all vertices in first-appearance order (deterministic)."""
        seen: dict[str, None] = {}
        for u, v in self.edges:
            seen.setdefault(u, None)
            seen.setdefault(v, None)
        return list(seen)

    def adjacency(self) -> dict[str, list[str]]:
        """Build an adjacency list with each neighbor list sorted."""
        adj: dict[str, list[str]] = {v: [] for v in self.vertices()}
        for u, v in self.edges:
            adj[u].append(v)
            if not self.directed:
                adj[v].append(u)
        for neighbors in adj.values():
            neighbors.sort()
        return adj


def bfs_visit_order(graph: Graph, start: str) -> list[str]:
    """Return the vertices in the order a breadth-first search visits them."""
    adj = graph.adjacency()
    if start not in adj:
        raise KeyError(f"start vertex {start!r} is not in the graph")

    visited: set[str] = {start}
    order: list[str] = []
    queue: deque[str] = deque([start])

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order


def main() -> None:
    edges = (
        ("A", "B"),
        ("A", "C"),
        ("B", "D"),
        ("C", "D"),
        ("C", "E"),
        ("D", "F"),
        ("E", "F"),
        ("G", "H"),  # disconnected component
    )

    undirected = Graph(edges)
    directed = Graph(edges, directed=True)

    print("Vertices:", undirected.vertices())
    print("BFS from A (undirected):", bfs_visit_order(undirected, "A"))
    print("BFS from A (directed):  ", bfs_visit_order(directed, "A"))
    print("BFS from G (undirected):", bfs_visit_order(undirected, "G"))
    print("BFS from F (directed):  ", bfs_visit_order(directed, "F"))


if __name__ == "__main__":
    main()
