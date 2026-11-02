# task: Use defaultdict(set) to build an undirected graph from hardcoded edges and print each node's sorted neighbors.
from collections import defaultdict


def build_graph(edges: list[tuple[str, str]]) -> defaultdict[str, set[str]]:
    graph: defaultdict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        graph[a].add(b)
        graph[b].add(a)
    return graph


def main() -> None:
    edges: list[tuple[str, str]] = [
        ("alice", "bob"),
        ("alice", "carol"),
        ("bob", "dave"),
        ("carol", "dave"),
        ("dave", "erin"),
        ("frank", "grace"),
        ("erin", "alice"),
        ("heidi", "heidi"),
    ]

    graph = build_graph(edges)

    for node in sorted(graph):
        neighbors = sorted(graph[node])
        print(f"{node}: {', '.join(neighbors)}")


if __name__ == "__main__":
    main()
