# task: Recursively count the simple paths between two fixed vertices in a small hard-coded undirected graph.
from __future__ import annotations


EDGES: list[tuple[str, str]] = [
    ("A", "B"),
    ("A", "C"),
    ("B", "C"),
    ("B", "D"),
    ("C", "D"),
    ("C", "E"),
    ("D", "E"),
    ("D", "F"),
    ("E", "F"),
]

START = "A"
GOAL = "F"


def build_adjacency(edges: list[tuple[str, str]]) -> dict[str, list[str]]:
    """Build a sorted adjacency list for an undirected graph."""
    adj: dict[str, set[str]] = {}
    for u, v in edges:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)
    return {vertex: sorted(neighbors) for vertex, neighbors in sorted(adj.items())}


def count_simple_paths(
    adj: dict[str, list[str]],
    node: str,
    target: str,
    visited: set[str],
) -> int:
    """Recursively count simple paths from node to target."""
    if node == target:
        return 1
    visited.add(node)
    total = 0
    for neighbor in adj[node]:
        if neighbor not in visited:
            total += count_simple_paths(adj, neighbor, target, visited)
    visited.remove(node)
    return total


def list_simple_paths(
    adj: dict[str, list[str]],
    node: str,
    target: str,
    path: list[str],
    results: list[tuple[str, ...]],
) -> None:
    """Recursively collect every simple path from node to target."""
    if node == target:
        results.append(tuple(path))
        return
    for neighbor in adj[node]:
        if neighbor not in path:
            path.append(neighbor)
            list_simple_paths(adj, neighbor, target, path, results)
            path.pop()


def main() -> None:
    adj = build_adjacency(EDGES)

    print("Graph adjacency (sorted):")
    for vertex, neighbors in adj.items():
        print(f"  {vertex}: {', '.join(neighbors)}")

    count = count_simple_paths(adj, START, GOAL, set())

    paths: list[tuple[str, ...]] = []
    list_simple_paths(adj, START, GOAL, [START], paths)
    paths.sort()

    assert count == len(paths), "counting and enumeration disagree"

    print()
    print(f"Simple paths from {START} to {GOAL}: {count}")
    print("All paths:")
    for path in paths:
        print("  " + " -> ".join(path))


if __name__ == "__main__":
    main()
