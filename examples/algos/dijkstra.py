"""Dijkstra shortest paths on a generated weighted graph."""
import heapq
import sys

SMALL = "--small" in sys.argv
NODES = 400 if SMALL else 150_000
DEGREE = 3

seed = 424242


def rnd():
    global seed
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    return seed


def build_graph(n):
    graph = {}
    for node in range(n):
        graph[node] = []
    for node in range(n):
        for _ in range(DEGREE):
            other = rnd() % n
            weight = 1 + rnd() % 200
            graph[node].append((other, weight))
            graph[other].append((node, weight))
    return graph


graph = build_graph(NODES)
distance = [None] * NODES
distance[0] = 0
queue = [(0, 0)]
while queue:
    cost, node = heapq.heappop(queue)
    if distance[node] != cost:
        continue
    for other, weight in graph[node]:
        candidate = cost + weight
        if distance[other] is None or candidate < distance[other]:
            distance[other] = candidate
            heapq.heappush(queue, (candidate, other))

reachable = 0
total = 0
furthest = 0
for value in distance:
    if value is not None:
        reachable += 1
        total += value
        if value > furthest:
            furthest = value

print("nodes", NODES)
print("reachable", reachable)
print("checksum", total)
print("furthest", furthest)
print("source", distance[0])
