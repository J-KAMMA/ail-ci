from collections import defaultdict, deque


def build_graph(edges: list[tuple[str, str]]) -> defaultdict[str, list[str]]:
    graph: defaultdict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        graph[src].append(dst)
        graph[dst].append(src)
    return graph


def bfs(graph: defaultdict[str, list[str]], start: str) -> dict[str, int]:
    dist = {start: 0}
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in graph[node]:
            if nxt not in dist:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def main() -> int:
    edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("d", "e")]
    graph = build_graph(edges)
    for node in sorted(graph):
        print(node, sorted(graph[node]), len(graph[node]))
    dist = bfs(graph, "a")
    for node in sorted(dist):
        print(node, dist[node])
    print(len(dist), dist.get("z", -1), "z" in dist)
    marks: defaultdict[str, set[str]] = defaultdict(set)
    marks["a"].add("x")
    marks["a"].add("y")
    marks["a"].add("x")
    marks["b"].update(["y", "z"])
    marks["a"].discard("x")
    marks["a"].remove("y")
    print(sorted(marks["a"]), sorted(marks["b"]), len(marks["a"]), "z" in marks["b"])
    counts: defaultdict[int, int] = defaultdict(int)
    for node in dist:
        counts[dist[node]] += 1
    for level in sorted(counts):
        print(level, counts[level])
    print(counts[99], len(counts))
    return 0


main()
