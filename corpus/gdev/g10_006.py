# task: Write a script that produces a topological ordering of a hardcoded directed acyclic graph using Kahn's algorithm and prints it.
from collections import deque
from typing import Dict, List


def build_graph() -> Dict[str, List[str]]:
    """Return a hardcoded DAG as an adjacency list (node -> list of successors)."""
    return {
        "shop": ["cook", "drive"],
        "wake": ["shower", "cook"],
        "shower": ["dress", "leave"],
        "dress": ["leave"],
        "cook": ["eat"],
        "eat": ["leave"],
        "drive": ["leave"],
        "leave": [],
    }


def kahn_topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """Return a topological ordering of the graph using Kahn's algorithm.

    Raises ValueError if the graph contains a cycle.
    """
    in_degree: Dict[str, int] = {node: 0 for node in graph}
    for node in graph:
        for neighbor in graph[node]:
            in_degree[neighbor] = in_degree.get(neighbor, 0) + 1

    # Seed the queue with zero in-degree nodes in sorted order for determinism.
    ready = sorted(node for node, deg in in_degree.items() if deg == 0)
    queue: deque[str] = deque(ready)

    order: List[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        newly_ready: List[str] = []
        for neighbor in sorted(graph.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                newly_ready.append(neighbor)
        for neighbor in sorted(newly_ready):
            queue.append(neighbor)

    if len(order) != len(in_degree):
        raise ValueError("graph contains a cycle; no topological ordering exists")
    return order


def main() -> None:
    graph = build_graph()
    order = kahn_topological_sort(graph)
    print("Topological ordering:")
    for index, node in enumerate(order, start=1):
        print(f"{index}. {node}")


if __name__ == "__main__":
    main()
