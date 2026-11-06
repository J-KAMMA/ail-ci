# task: Write a script that detects whether a hardcoded undirected graph is bipartite using BFS two-coloring and prints the result.
from collections import deque


def build_adjacency(num_vertices: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Build an undirected adjacency list from an edge list."""
    adj: list[list[int]] = [[] for _ in range(num_vertices)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def two_color(adj: list[list[int]]) -> tuple[bool, list[int], tuple[int, int] | None]:
    """
    Attempt a BFS two-coloring of an undirected graph.

    Returns (is_bipartite, colors, conflict_edge).
    colors[v] is 0 or 1 for colored vertices (all vertices end up colored).
    conflict_edge is an edge (u, v) whose endpoints received the same color,
    or None if the graph is bipartite.
    """
    n = len(adj)
    colors: list[int] = [-1] * n

    for start in range(n):  # handles disconnected graphs deterministically
        if colors[start] != -1:
            continue
        colors[start] = 0
        queue: deque[int] = deque([start])
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if colors[v] == -1:
                    colors[v] = 1 - colors[u]
                    queue.append(v)
                elif colors[v] == colors[u]:
                    return False, colors, (u, v)
    return True, colors, None


def describe_partition(colors: list[int]) -> str:
    side0 = [str(v) for v, c in enumerate(colors) if c == 0]
    side1 = [str(v) for v, c in enumerate(colors) if c == 1]
    return f"part A = {{{', '.join(side0)}}}, part B = {{{', '.join(side1)}}}"


def main() -> None:
    graphs: list[tuple[str, int, list[tuple[int, int]]]] = [
        (
            "Even cycle C6",
            6,
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0)],
        ),
        (
            "Odd cycle C5",
            5,
            [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)],
        ),
        (
            "Disconnected: path P4 plus triangle",
            7,
            [(0, 1), (1, 2), (2, 3), (4, 5), (5, 6), (6, 4)],
        ),
        (
            "Complete bipartite K3,2",
            5,
            [(0, 3), (0, 4), (1, 3), (1, 4), (2, 3), (2, 4)],
        ),
    ]

    for name, num_vertices, edges in graphs:
        adj = build_adjacency(num_vertices, edges)
        is_bipartite, colors, conflict = two_color(adj)
        print(f"Graph: {name}")
        if is_bipartite:
            print("  Result: bipartite")
            print(f"  {describe_partition(colors)}")
        else:
            assert conflict is not None
            u, v = conflict
            print("  Result: not bipartite")
            print(f"  Conflicting edge: ({u}, {v}) both colored {colors[u]}")
        print()


if __name__ == "__main__":
    main()
