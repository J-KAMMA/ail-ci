# task: Write a script that counts the connected components of a hardcoded undirected graph using iterative DFS and prints the count.
from collections import defaultdict
from typing import Iterable


def build_graph(edges: Iterable[tuple[int, int]], vertices: Iterable[int]) -> dict[int, list[int]]:
    adjacency: dict[int, list[int]] = defaultdict(list)
    for v in vertices:
        adjacency[v]
    for u, v in edges:
        adjacency[u].append(v)
        adjacency[v].append(u)
    return adjacency


def count_connected_components(adjacency: dict[int, list[int]]) -> int:
    visited: set[int] = set()
    count = 0
    for start in sorted(adjacency):
        if start in visited:
            continue
        count += 1
        visited.add(start)
        stack: list[int] = [start]
        while stack:
            node = stack.pop()
            for neighbor in adjacency[node]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
    return count


def main() -> None:
    vertices = range(1, 16)
    edges = [
        (1, 2),
        (2, 3),
        (3, 1),
        (4, 5),
        (6, 7),
        (7, 8),
        (8, 9),
        (9, 6),
        (10, 10),
        (11, 12),
        (12, 13),
        (14, 15),
        (15, 14),
    ]
    adjacency = build_graph(edges, vertices)
    components = count_connected_components(adjacency)
    print(f"Number of connected components: {components}")


if __name__ == "__main__":
    main()
