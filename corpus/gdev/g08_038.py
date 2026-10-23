# task: Use backtracking to enumerate all Hamiltonian cycles in the complete graph K4 and print the count.
from typing import Iterator


def complete_graph_adjacency(n: int) -> dict[int, list[int]]:
    """Return the adjacency lists of the complete graph K_n on vertices 0..n-1."""
    return {v: [u for u in range(n) if u != v] for v in range(n)}


def hamiltonian_cycles(adj: dict[int, list[int]]) -> Iterator[tuple[int, ...]]:
    """
    Yield each undirected Hamiltonian cycle exactly once.

    Each cycle is reported as a vertex sequence starting at the smallest
    vertex (0), and the direction is fixed by requiring the second vertex
    to be smaller than the last vertex, which removes reversed duplicates.
    """
    vertices = sorted(adj)
    n = len(vertices)
    if n < 3:
        return

    start = vertices[0]
    path: list[int] = [start]
    on_path: set[int] = {start}

    def extend() -> Iterator[tuple[int, ...]]:
        if len(path) == n:
            last = path[-1]
            if start in adj[last] and path[1] < path[-1]:
                yield tuple(path + [start])
            return
        current = path[-1]
        for nxt in adj[current]:
            if nxt not in on_path:
                path.append(nxt)
                on_path.add(nxt)
                yield from extend()
                on_path.remove(nxt)
                path.pop()

    yield from extend()


def main() -> None:
    n = 4
    adj = complete_graph_adjacency(n)
    cycles = list(hamiltonian_cycles(adj))
    print(f"Hamiltonian cycles in K{n}: {len(cycles)}")
    for cycle in cycles:
        print(" -> ".join(str(v) for v in cycle))


if __name__ == "__main__":
    main()
