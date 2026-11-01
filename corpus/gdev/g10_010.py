# task: Write a script that finds all strongly connected components of a hardcoded directed graph using Tarjan's algorithm and prints them.
from typing import Dict, List, Set


def build_nodes(graph: Dict[str, List[str]]) -> List[str]:
    """Return every node mentioned in the graph (as a source or a target), sorted."""
    nodes: Set[str] = set(graph.keys())
    for targets in graph.values():
        nodes.update(targets)
    return sorted(nodes)


def tarjan_scc(graph: Dict[str, List[str]]) -> List[List[str]]:
    """
    Find all strongly connected components using Tarjan's algorithm.

    Nodes and neighbours are visited in sorted order, and each component
    and the final list of components are sorted, so the output is deterministic.
    """
    index_counter = 0
    index: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    components: List[List[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index_counter
        index[v] = index_counter
        lowlink[v] = index_counter
        index_counter += 1
        stack.append(v)
        on_stack.add(v)

        for w in sorted(graph.get(v, [])):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index[w])

        if lowlink[v] == index[v]:
            component: List[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                component.append(w)
                if w == v:
                    break
            components.append(sorted(component))

    for node in build_nodes(graph):
        if node not in index:
            strongconnect(node)

    return sorted(components)


def main() -> None:
    graph: Dict[str, List[str]] = {
        "A": ["B"],
        "B": ["C", "E"],
        "C": ["D"],
        "D": ["C", "F"],
        "E": ["A", "F"],
        "F": ["G"],
        "G": ["H"],
        "H": ["F", "I"],
        "I": [],
        "J": ["I", "K"],
        "K": ["J"],
    }

    components = tarjan_scc(graph)

    print(f"Number of strongly connected components: {len(components)}")
    for i, component in enumerate(components, start=1):
        print(f"SCC {i}: {', '.join(component)}")


if __name__ == "__main__":
    main()
