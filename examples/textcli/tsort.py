"""tsort.py: read `a b` pairs from stdin and print a topological order."""
import heapq
import sys


def topo_order(before: list[str], after_names: list[str]) -> bool:
    slots: dict[str, int] = {}
    nodes: list[list[str]] = []
    indegree: dict[str, int] = {}
    for k in range(len(before)):
        left = before[k]
        right = after_names[k]
        for name in (left, right):
            if name not in slots:
                slots[name] = len(nodes)
                nodes.append([])
                indegree[name] = 0
        node = nodes[slots[left]]
        node.append(right)
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
        for follower in node:
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
        left, right = line.split()
        before.append(left)
        after_names.append(right)
    if not topo_order(before, after_names):
        print("tsort: cycle", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
