from graphlib import TopologicalSorter


sorter = TopologicalSorter()
sorter.add("clean")
sorter.add("generate")
sorter.add("compile", "clean")
sorter.add("compile", "generate")
sorter.add("link", "compile", "compile")
sorter.add("test", "link")
sorter.add("package", "link")
sorter.add("deploy", "package", "test")

order = list(sorter.static_order())
print("build:", order)
print("first:", order[0])
print("last:", order[-1])

position = {}
for index, node in enumerate(order):
    position[node] = index

print("clean before compile:", position["clean"] < position["compile"])
print("compile before link:", position["compile"] < position["link"])
print("test before deploy:", position["test"] < position["deploy"])
