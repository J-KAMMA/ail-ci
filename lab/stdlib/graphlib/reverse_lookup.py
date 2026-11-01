from graphlib import TopologicalSorter, CycleError


edges = [(1, 2), (1, 3), (2, 4), (3, 4), (4, 5)]
graph = {}
for before, after in edges:
    if after not in graph:
        graph[after] = []
    graph[after].append(before)
    if before not in graph:
        graph[before] = []

sorter = TopologicalSorter()
for node in graph:
    sorter.add(node)
    for pred in graph[node]:
        sorter.add(node, pred)

order = list(sorter.static_order())
print("nodes:", order)
print("first:", order[0])
print("last:", order[-1])
print("position 4:", order.index(4))

cyclic = TopologicalSorter({"x": ["z"], "y": ["x"], "z": ["y"], "free": []})
try:
    cyclic.prepare()
except CycleError as exc:
    print("cycle:", exc.args[1])
print("partial:", cyclic.get_ready())
print("active:", cyclic.is_active())
