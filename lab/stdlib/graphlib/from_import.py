from graphlib import TopologicalSorter
from graphlib import CycleError


def order_for(graph):
    sorter = TopologicalSorter(graph)
    return list(sorter.static_order())


def main():
    deps = {
        "setup": [],
        "build": ["setup"],
        "lint": ["setup"],
        "ship": ["build", "lint"],
    }
    print("order:", order_for(deps))

    bad = {"x": ["y"], "y": ["x"]}
    try:
        order_for(bad)
    except CycleError as exc:
        print("caught:", exc.args[0])
        print("nodes:", exc.args[1])

    print("after:", order_for({"only": []}))


main()
