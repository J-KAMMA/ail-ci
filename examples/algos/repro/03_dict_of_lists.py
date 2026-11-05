"""Reproducer: an int-keyed dict whose lists hold tuples keeps adjacency lists off the typed path."""

graph = {}
for node in range(4):
    graph[node] = []
    graph[node].append((node + 1, node + 2))

total = 0
for node in graph:
    for edge in graph[node]:
        total += edge[0]
print(total)
