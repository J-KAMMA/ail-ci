"""networkx Dijkstra / BFS vs rustworkx on the same deterministic graph.

CPython and hybrid both use networkx, so their stdout must match byte for byte.  The Rust
rewrite (rustworkx) is a separate implementation and is measured as the rewrite baseline.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _impl import LCG, impl, load_hybrid  # noqa: E402

N = 1200
M = 80000
SOURCES = 100


def graph_edges():
    rng = LCG(20261109)
    seen = set()
    edges = []
    while len(edges) < M:
        u = rng.below(N)
        v = rng.below(N)
        if u == v or (u, v) in seen:
            continue
        seen.add((u, v))
        edges.append((u, v, 1 + rng.below(9)))
    return edges


def main():
    mode = impl()
    edges = graph_edges()
    sources = [(i * 37 + 11) % N for i in range(SOURCES)]

    if mode == 'rust':
        import rustworkx as rx
        g = rx.PyDiGraph()
        g.add_nodes_from(range(N))
        g.add_edges_from([(u, v, w) for u, v, w in edges])
        total = cnt = btotal = bcnt = 0
        for s in sources:
            d = rx.digraph_dijkstra_shortest_path_lengths(g, s, lambda w: w)
            total += int(sum(d.values()))
            cnt += len(d) + (0 if s in d else 1)
            b = rx.digraph_dijkstra_shortest_path_lengths(g, s, lambda w: 1)
            btotal += int(sum(b.values()))
            bcnt += len(b) + (0 if s in b else 1)
        print('weighted', total, cnt)
        print('unweighted', btotal, bcnt)
        return

    import networkx as nx
    if mode == 'hybrid':
        weighted = load_hybrid('weighted')
        unweighted = load_hybrid('unweighted')
    else:
        from networkx.algorithms.shortest_paths import weighted, unweighted

    G = nx.DiGraph()
    G.add_nodes_from(range(N))
    G.add_weighted_edges_from(edges)
    total = cnt = btotal = bcnt = 0
    for s in sources:
        d = weighted.single_source_dijkstra_path_length(G, s)
        total += sum(d.values())
        cnt += len(d)
        b = unweighted.single_source_shortest_path_length(G, s)
        btotal += sum(b.values())
        bcnt += len(b)
    print('weighted', total, cnt)
    print('unweighted', btotal, bcnt)


if __name__ == '__main__':
    main()
