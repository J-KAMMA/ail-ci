"""Driver for graph_search: BFS and DFS over a generated graph."""
import graph_search as m

NODES = 60000
FANOUT = 8
ROUNDS = 22


def main() -> None:
    adj = m.build_graph(NODES, FANOUT)
    reach = 0
    visited = 0
    for r in range(ROUNDS):
        reach += m.bfs_reach(adj, r)
        visited += m.dfs_count(adj, NODES - 1 - r)
    print("nodes", len(adj))
    print("edges", m.degree_sum(adj))
    print("max_degree", m.max_degree(adj))
    print("above", m.edges_above(adj, NODES // 2))
    print("reach", reach)
    print("visited", visited)


main()
