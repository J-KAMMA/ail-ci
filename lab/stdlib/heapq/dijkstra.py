import heapq


def main():
    graph = {
        "A": [("B", 4), ("C", 2)],
        "B": [("C", 5), ("D", 10)],
        "C": [("E", 3)],
        "D": [("F", 11)],
        "E": [("D", 4)],
        "F": [],
    }
    start = "A"
    distance = {}
    for node in graph:
        distance[node] = 10 ** 9
    distance[start] = 0
    heap = [(0, start)]
    done = set()
    while heap:
        cost, node = heapq.heappop(heap)
        if node in done:
            continue
        done.add(node)
        for neighbour, weight in graph[node]:
            candidate = cost + weight
            if candidate < distance[neighbour]:
                distance[neighbour] = candidate
                heapq.heappush(heap, (candidate, neighbour))
    for node in sorted(distance):
        print(node, distance[node])
    print("visited", sorted(done))


main()
