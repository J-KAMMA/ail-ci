# task: Write a script that checks a hardcoded directed graph for a Hamiltonian path of small size by brute-force DFS and prints one path found or None.
from typing import Dict, List, Optional, Set


# Hardcoded directed graph: vertex -> list of out-neighbours.
GRAPH: Dict[int, List[int]] = {
    0: [1, 2],
    1: [2, 3],
    2: [3, 4],
    3: [4, 5],
    4: [5, 0],
    5: [0],
}


def all_vertices(graph: Dict[int, List[int]]) -> List[int]:
    """Return every vertex (sources and targets), sorted for determinism."""
    vertices: Set[int] = set(graph)
    for targets in graph.values():
        vertices.update(targets)
    return sorted(vertices)


def find_hamiltonian_path(graph: Dict[int, List[int]]) -> Optional[List[int]]:
    """Find one Hamiltonian path by brute-force DFS, or return None."""
    vertices = all_vertices(graph)
    total = len(vertices)
    path: List[int] = []
    visited: Set[int] = set()

    def dfs(vertex: int) -> bool:
        path.append(vertex)
        visited.add(vertex)
        if len(path) == total:
            return True
        for neighbour in sorted(graph.get(vertex, [])):
            if neighbour not in visited and dfs(neighbour):
                return True
        path.pop()
        visited.remove(vertex)
        return False

    for start in vertices:
        if dfs(start):
            return list(path)
    return None


def main() -> None:
    result = find_hamiltonian_path(GRAPH)
    print(result)


if __name__ == "__main__":
    main()
