from graphlib import TopologicalSorter


def report(label, exc):
    print(label + ":", type(exc).__name__, exc)


sorter = TopologicalSorter()
try:
    sorter.get_ready()
except ValueError as exc:
    report("get_ready before prepare", exc)

try:
    sorter.is_active()
except ValueError as exc:
    report("is_active before prepare", exc)

try:
    sorter.done("a")
except ValueError as exc:
    report("done before prepare", exc)

sorter.add("a")
sorter.add("b", "a")
sorter.prepare()

try:
    sorter.done("zzz")
except ValueError as exc:
    report("done unknown", exc)

try:
    sorter.done("b")
except ValueError as exc:
    report("done not ready", exc)

ready = sorter.get_ready()
print("ready:", ready)
sorter.done("a")

try:
    sorter.done("a")
except ValueError as exc:
    report("done twice", exc)

try:
    sorter.add("c")
except ValueError as exc:
    report("add after prepare", exc)
