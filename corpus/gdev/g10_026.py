# task: Write a script that finds bridge edges in a hardcoded undirected graph using DFS discovery and low times and prints them sorted.
from typing import Optional


EDGES: list[tuple[str, str]] = [
    ("A", "B"),
    ("A", "C"),
    ("B", "C"),
    ("C", "D"),
    ("D", "E"),
    ("E", "F"),
    ("D", "G"),
    ("G", "H"),
    ("H", "I"),
    ("G", "I"),
    ("F", "J"),
    ("K", "L"),
]


def build_adjacency(edges: list[tuple[str, str]]) -> dict[str, list[tuple[str, int]]]:
    """Build an adjacency list where each entry stores (neighbor, edge_id)."""
    adj: dict[str, list[tuple[str, int]]] = {}
    for edge_id, (u, v) in enumerate(edges):
        adj.setdefault(u, []).append((v, edge_id))
        adj.setdefault(v, []).append((u, edge_id))
    return adj


def normalize_edge(u: str, v: str) -> tuple[str, str]:
    """Return an edge as a canonical (smaller, larger) pair."""
    return (u, v) if u <= v else (v, u)


def find_bridges(adj: dict[str, list[tuple[str, int]]]) -> list[tuple[str, str]]:
    """Find all bridge edges using DFS discovery times and low-link values."""
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    timer = 0
    bridges: list[tuple[str, str]] = []

    def dfs(u: str, parent_edge: Optional[int]) -> None:
        nonlocal timer
        disc[u] = timer
        low[u] = timer
        timer += 1

        for v, edge_id in adj[u]:
            if edge_id == parent_edge:
                continue  # do not reuse the edge we arrived through
            if v in disc:
                # Back edge (or forward view of one): tighten low[u].
                low[u] = min(low[u], disc[v])
            else:
                dfs(v, edge_id)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.append(normalize_edge(u, v))

    # Iterate in insertion order (deterministic) to cover every component.
    for node in adj:
        if node not in disc:
            dfs(node, None)

    return sorted(bridges)


def main() -> None:
    adj = build_adjacency(EDGES)
    bridges = find_bridges(adj)
    print(f"Number of bridges: {len(bridges)}")
    for u, v in bridges:
        print(f"{u}-{v}")


if __name__ == "__main__":
    main()
