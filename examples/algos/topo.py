"""Kahn topological sort of a generated directed acyclic graph."""
import collections
import sys

SMALL = "--small" in sys.argv
NODES = 2_500 if SMALL else 450_000
EDGES_PER_NODE = 2 if SMALL else 4

seed = 24680


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def build_graph(n, per_node):
    graph = {}
    indegree = [0] * n
    for node in range(n):
        graph[node] = []
    for node in range(n):
        for _ in range(per_node):
            if node + 1 >= n:
                continue
            other = node + 1 + rnd() % (n - node - 1)
            graph[node].append(other)
            indegree[other] += 1
    return graph, indegree


graph, indegree = build_graph(NODES, EDGES_PER_NODE)
queue = collections.deque()
for node in range(NODES):
    if indegree[node] == 0:
        queue.append(node)

order = []
while queue:
    node = queue.popleft()
    order.append(node)
    for other in graph[node]:
        indegree[other] -= 1
        if indegree[other] == 0:
            queue.append(other)

checksum = 0
for position, node in enumerate(order):
    checksum += (position + 1) * (node + 1)

print("nodes", NODES)
print("sorted", len(order))
print("checksum", checksum)
print("first", order[:8])
print("last", order[-1])
