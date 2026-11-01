from graphlib import TopologicalSorter


graph = {
    "app": ["lib", "config"],
    "lib": ["config"],
    "config": [],
    "test": ["app"],
}

sorter = TopologicalSorter(graph=graph)
sorter.add("app", "config")
sorter.add("extra")

order = list(sorter.static_order())
print("order:", order)
print("extra:", order.index("extra"))
print("config first:", order[0] == "config")

fresh = TopologicalSorter(graph={})
print("fresh:", list(fresh.static_order()))

single = TopologicalSorter()
single.add("only")
print("single:", list(single.static_order()))
