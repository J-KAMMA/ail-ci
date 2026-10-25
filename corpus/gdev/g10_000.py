# task: Write a script that performs breadth-first search on a hardcoded undirected graph of eight nodes starting from node 0 and prints the visitation order.
from collections import deque


def build_graph() -> dict[int, list[int]]:
    """Return a hardcoded undirected graph of eight nodes (0-7) as adjacency lists."""
    edges: list[tuple[int, int]] = [
        (0, 1),
        (0, 2),
        (1, 3),
        (1, 4),
        (2, 5),
        (2, 6),
        (4, 7),
        (5, 7),
    ]
    graph: dict[int, list[int]] = {node: [] for node in range(8)}
    for u, v in edges:
        graph[u].append(v)
        graph[v].append(u)
    for neighbors in graph.values():
        neighbors.sort()
    return graph


def bfs_order(graph: dict[int, list[int]], start: int) -> list[int]:
    """Return the nodes in the order they are visited by breadth-first search."""
    visited: set[int] = {start}
    order: list[int] = []
    queue: deque[int] = deque([start])

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order


def main() -> None:
    graph = build_graph()
    order = bfs_order(graph, 0)
    print("BFS visitation order from node 0:")
    print(" -> ".join(str(node) for node in order))


if __name__ == "__main__":
    main()
