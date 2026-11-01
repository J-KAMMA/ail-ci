# task: Write a script that finds all nodes reachable from a start node in a hardcoded graph using a visited set and breadth-first search.
from collections import deque


def bfs_reachable(graph: dict[str, list[str]], start: str) -> list[str]:
    """Return nodes reachable from start, in BFS visit order."""
    visited: set[str] = {start}
    order: list[str] = []
    queue: deque[str] = deque([start])

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order


def main() -> None:
    graph: dict[str, list[str]] = {
        "A": ["B", "C"],
        "B": ["D", "E"],
        "C": ["F"],
        "D": ["B"],
        "E": ["G"],
        "F": ["C", "H"],
        "G": [],
        "H": ["I"],
        "I": [],
        "J": ["K"],
        "K": ["J"],
    }

    start = "A"
    reachable = bfs_reachable(graph, start)

    print(f"Start node: {start}")
    print("BFS visit order:", " -> ".join(reachable))
    print("Reachable nodes (sorted):", ", ".join(sorted(reachable)))
    print(f"Count: {len(reachable)}")


if __name__ == "__main__":
    main()
