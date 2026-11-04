# task: Write a script that implements Bellman-Ford on a hardcoded graph with negative edge weights and prints the distance table.
from typing import Dict, List, Optional, Tuple


Edge = Tuple[str, str, int]


def bellman_ford(
    vertices: List[str],
    edges: List[Edge],
    source: str,
) -> Tuple[Dict[str, Optional[int]], Dict[str, Optional[str]], bool]:
    """Run Bellman-Ford from source.

    Returns (distance, predecessor, has_negative_cycle).
    Unreachable vertices have distance None.
    """
    dist: Dict[str, Optional[int]] = {v: None for v in vertices}
    pred: Dict[str, Optional[str]] = {v: None for v in vertices}
    dist[source] = 0

    def relax_once() -> bool:
        changed = False
        for u, v, w in edges:
            du = dist[u]
            if du is None:
                continue
            candidate = du + w
            dv = dist[v]
            if dv is None or candidate < dv:
                dist[v] = candidate
                pred[v] = u
                changed = True
        return changed

    for _ in range(len(vertices) - 1):
        if not relax_once():
            break

    has_negative_cycle = False
    for u, v, w in edges:
        du = dist[u]
        if du is not None and dist[v] is not None and du + w < dist[v]:
            has_negative_cycle = True
            break

    return dist, pred, has_negative_cycle


def reconstruct_path(
    pred: Dict[str, Optional[str]],
    target: str,
) -> List[str]:
    """Rebuild the path from the source to target using predecessors."""
    path: List[str] = []
    seen: set[str] = set()
    node: Optional[str] = target
    while node is not None and node not in seen:
        seen.add(node)
        path.append(node)
        node = pred[node]
    path.reverse()
    return path


def print_distance_table(
    vertices: List[str],
    dist: Dict[str, Optional[int]],
    pred: Dict[str, Optional[str]],
) -> None:
    header = f"{'Vertex':<8}{'Distance':>10}  {'Path'}"
    print(header)
    print("-" * len(header))
    for v in vertices:
        d = dist[v]
        d_text = "inf" if d is None else str(d)
        if d is None:
            path_text = "-"
        else:
            path_text = " -> ".join(reconstruct_path(pred, v))
        print(f"{v:<8}{d_text:>10}  {path_text}")


def main() -> None:
    vertices: List[str] = ["A", "B", "C", "D", "E", "F"]
    edges: List[Edge] = [
        ("A", "B", 4),
        ("A", "C", 5),
        ("B", "C", -3),
        ("B", "D", 6),
        ("C", "E", 2),
        ("D", "B", -2),
        ("D", "F", 3),
        ("E", "D", -1),
        ("E", "F", 4),
        ("C", "F", 8),
    ]
    source = "A"

    print(f"Bellman-Ford from source {source}")
    print(f"Vertices: {len(vertices)}, Edges: {len(edges)}")
    print()

    dist, pred, negative_cycle = bellman_ford(vertices, edges, source)

    if negative_cycle:
        print("Negative-weight cycle reachable from source; distances undefined.")
        return

    print_distance_table(vertices, dist, pred)


if __name__ == "__main__":
    main()
