from graphlib import TopologicalSorter


graph = {
    "root": [],
    "left": ["root"],
    "right": ["root"],
    "merge": ["left", "right"],
    "report": ["merge"],
}

sorter = TopologicalSorter(graph)
sorter.prepare()
layers = []

while sorter.is_active():
    ready = sorter.get_ready()
    layers.append(list(ready))
    for node in ready:
        sorter.done(node)

for index, layer in enumerate(layers):
    print(index, layer)

print("layer count:", len(layers))
print("total nodes:", sum(len(layer) for layer in layers))
