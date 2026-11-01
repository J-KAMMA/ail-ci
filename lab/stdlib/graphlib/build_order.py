from graphlib import TopologicalSorter


graph = {
    "compile": ["parse", "typecheck"],
    "link": ["compile"],
    "package": ["link", "docs"],
    "docs": [],
    "parse": [],
    "typecheck": ["parse"],
    "test": ["link"],
}

order = list(TopologicalSorter(graph).static_order())
print("order:", order)
print("count:", len(order))
print("first:", order[0])
print("last:", order[-1])

seen = set()
for node in order:
    for pred in graph[node]:
        if pred not in seen:
            print("missing predecessor:", pred)
    seen.add(node)
print("checked:", len(seen))
