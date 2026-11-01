from graphlib import TopologicalSorter, CycleError


graph = {
    "a": ["c"],
    "b": ["a"],
    "c": ["b"],
    "d": [],
}

sorter = TopologicalSorter(graph)
try:
    sorter.prepare()
    print("no cycle")
except CycleError as exc:
    print("type:", type(exc).__name__)
    print("args:", len(exc.args))
    print("message:", exc.args[0])
    print("cycle:", exc.args[1])
    print("text:", exc)

print("ready after cycle:", sorter.get_ready())
print("active after cycle:", sorter.is_active())
print("done free node")
sorter.done("d")
print("active at end:", sorter.is_active())
