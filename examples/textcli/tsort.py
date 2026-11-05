"""tsort.py: read `a b` pairs from stdin and print a topological order."""
import heapq
import sys
from dataclasses import dataclass


@dataclass
class Node:
    followers: list[str]


def topo_order(before: list[str], after_names: list[str]) -> bool:
    slots: dict[str, int] = {}
    nodes: list[Node] = []
    indegree: dict[str, int] = {}
    for k in range(len(before)):
        left = before[k]
        right = after_names[k]
        if left not in slots:
            slots[left] = len(nodes)
            nodes.append(Node([]))
            indegree[left] = 0
        if right not in slots:
            slots[right] = len(nodes)
            nodes.append(Node([]))
            indegree[right] = 0
        node = nodes[slots[left]]
        node.followers.append(right)
        indegree[right] = indegree[right] + 1
    ready: list[str] = []
    for name in indegree:
        if indegree[name] == 0:
            heapq.heappush(ready, name)
    order: list[str] = []
    while len(ready) > 0:
        name = heapq.heappop(ready)
        order.append(name)
        node = nodes[slots[name]]
        for follower in node.followers:
            indegree[follower] = indegree[follower] - 1
            if indegree[follower] == 0:
                heapq.heappush(ready, follower)
    if len(order) != len(indegree):
        return False
    for name in order:
        print(name)
    return True


def main() -> int:
    before = []
    after_names = []
    for raw in sys.stdin:
        line = raw.strip()
        if line == "":
            continue
        fields = line.split()
        if len(fields) != 2:
            print("tsort: input must be pairs", file=sys.stderr)
            return 1
        before.append(fields[0])
        after_names.append(fields[1])
    if len(before) == 0:
        return 0
    if not topo_order(before, after_names):
        print("tsort: cycle", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
