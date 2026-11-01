from graphlib import TopologicalSorter


sorter = TopologicalSorter()
print("empty order:", list(sorter.static_order()))

other = TopologicalSorter({})
other.prepare()
print("ready:", other.get_ready())
print("active:", other.is_active())
print("ready again:", other.get_ready())

try:
    other.prepare()
except ValueError as exc:
    print("prepare twice:", exc)

try:
    other.add("late")
except ValueError as exc:
    print("add after prepare:", exc)

try:
    other.done("missing")
except ValueError as exc:
    print("done missing:", exc)
