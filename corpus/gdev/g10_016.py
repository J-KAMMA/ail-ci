# task: Write a script that computes all-pairs shortest distances on a hardcoded weighted graph using the Floyd-Warshall algorithm and prints the matrix.
import math
from typing import Optional


def floyd_warshall(dist: list[list[float]]) -> list[list[float]]:
    """Compute all-pairs shortest distances in place-safe manner on a copy."""
    n = len(dist)
    result = [row[:] for row in dist]
    for k in range(n):
        for i in range(n):
            if result[i][k] == math.inf:
                continue
            for j in range(n):
                candidate = result[i][k] + result[k][j]
                if candidate < result[i][j]:
                    result[i][j] = candidate
    return result


def format_cell(value: float, width: int) -> str:
    if value == math.inf:
        text = "INF"
    else:
        text = str(int(value)) if float(value).is_integer() else f"{value:.2f}"
    return text.rjust(width)


def print_matrix(labels: list[str], matrix: list[list[float]]) -> None:
    width = max(len(label) for label in labels)
    cell_width = max(
        max(len(format_cell(v, 0)) for row in matrix for v in row),
        max(len(label) for label in labels),
    )
    header = " " * (width + 1) + " ".join(label.rjust(cell_width) for label in labels)
    print(header)
    for label, row in zip(labels, matrix):
        cells = " ".join(format_cell(v, cell_width) for v in row)
        print(f"{label.ljust(width)} {cells}")


def main() -> None:
    labels: list[str] = ["A", "B", "C", "D", "E", "F"]
    index: dict[str, int] = {name: i for i, name in enumerate(labels)}

    # Directed weighted edges: (source, target, weight)
    edges: list[tuple[str, str, float]] = [
        ("A", "B", 4),
        ("A", "C", 2),
        ("B", "C", 5),
        ("B", "D", 10),
        ("C", "E", 3),
        ("E", "D", 4),
        ("D", "F", 11),
        ("E", "F", 7),
        ("F", "A", 1),
    ]

    n = len(labels)
    dist: list[list[float]] = [
        [0.0 if i == j else math.inf for j in range(n)] for i in range(n)
    ]
    for src, dst, weight in edges:
        i, j = index[src], index[dst]
        dist[i][j] = min(dist[i][j], weight)

    result = floyd_warshall(dist)

    print("All-pairs shortest distances (Floyd-Warshall):")
    print_matrix(labels, result)


if __name__ == "__main__":
    main()
