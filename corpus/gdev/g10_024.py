# task: Write a script that finds all simple paths between two fixed nodes in a small hardcoded undirected graph using DFS backtracking and prints them sorted.
from typing import Dict, List


def build_graph() -> Dict[str, List[str]]:
    """Return a small hardcoded undirected graph as an adjacency list."""
    edges = [
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
    graph: Dict[str, List[str]] = {}
    for u, v in edges:
        graph.setdefault(u, []).append(v)
        graph.setdefault(v, []).append(u)
    for node in graph:
        graph[node].sort()
    return graph


def find_simple_paths(
    graph: Dict[str, List[str]], start: str, goal: str
) -> List[List[str]]:
    """Find all simple paths from start to goal using DFS backtracking."""
    paths: List[List[str]] = []
    path: List[str] = [start]
    visited: set[str] = {start}

    def dfs(node: str) -> None:
        if node == goal:
            paths.append(list(path))
            return
        for neighbor in graph.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            path.append(neighbor)
            dfs(neighbor)
            path.pop()
            visited.remove(neighbor)

    dfs(start)
    return paths


def main() -> None:
    graph = build_graph()
    start = "A"
    goal = "F"

    paths = find_simple_paths(graph, start, goal)
    paths.sort()

    print(f"Simple paths from {start} to {goal}: {len(paths)} found")
    for i, p in enumerate(paths, start=1):
        print(f"{i:3d}. {' -> '.join(p)}")


if __name__ == "__main__":
    main()
