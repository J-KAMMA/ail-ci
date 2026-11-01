from graphlib import TopologicalSorter


graph = {
    "a": [],
    "b": ["a"],
    "c": ["a"],
    "d": ["b"],
    "e": ["c", "d"],
    "f": ["e"],
}

order = list(TopologicalSorter(graph).static_order())
print("topological:", order)

depth = {}
for node in order:
    best = 0
    for pred in graph[node]:
        candidate = depth[pred] + 1
        if candidate > best:
            best = candidate
    depth[node] = best

for node in graph:
    print(node, depth[node])

print("max depth:", max(depth.values()))
print("order is valid:", order.index("a") < order.index("f"))
