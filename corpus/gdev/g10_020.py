# task: Write a script that determines whether a hardcoded undirected graph is a tree by checking connectivity and edge count and prints the verdict.
from collections import deque
from typing import Dict, List, Tuple


def build_adjacency(num_nodes: int, edges: List[Tuple[int, int]]) -> Dict[int, List[int]]:
    adj: Dict[int, List[int]] = {node: [] for node in range(num_nodes)}
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def is_connected(adj: Dict[int, List[int]]) -> bool:
    if not adj:
        return True
    start = min(adj)
    visited = {start}
    queue: deque[int] = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited) == len(adj)


def is_tree(num_nodes: int, edges: List[Tuple[int, int]]) -> Tuple[bool, str]:
    if num_nodes == 0:
        return False, "graph has no nodes"

    seen_edges = set()
    for u, v in edges:
        if u == v:
            return False, f"self-loop at node {u}"
        key = (min(u, v), max(u, v))
        if key in seen_edges:
            return False, f"duplicate edge {key[0]}-{key[1]}"
        seen_edges.add(key)

    adj = build_adjacency(num_nodes, edges)

    if not is_connected(adj):
        return False, "graph is not connected"

    if len(edges) != num_nodes - 1:
        return False, (
            f"edge count is {len(edges)}, expected {num_nodes - 1} for a tree"
        )

    return True, "graph is a tree"


def main() -> None:
    num_nodes = 7
    edges: List[Tuple[int, int]] = [
        (0, 1),
        (0, 2),
        (1, 3),
        (1, 4),
        (2, 5),
        (5, 6),
    ]

    is_a_tree, reason = is_tree(num_nodes, edges)
    verdict = "YES" if is_a_tree else "NO"
    print(f"Nodes: {num_nodes}")
    print(f"Edges: {len(edges)}")
    print(f"Is tree: {verdict}")
    print(f"Reason: {reason}")


if __name__ == "__main__":
    main()
