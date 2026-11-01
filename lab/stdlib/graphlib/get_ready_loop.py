from graphlib import TopologicalSorter


graph = {
    "a": [],
    "b": ["a"],
    "c": ["a"],
    "d": ["b", "c"],
    "e": ["d"],
}

sorter = TopologicalSorter(graph)
sorter.prepare()
batches = []

while sorter.is_active():
    ready = sorter.get_ready()
    batches.append(ready)
    print("ready:", ready)
    for node in ready:
        sorter.done(node)

print("batches:", len(batches))
print("sizes:", [len(batch) for batch in batches])
print("active:", sorter.is_active())
print("empty after finish:", sorter.get_ready())
