import heapq


def score(point):
    return point[0] * point[0] + point[1] * point[1]


def main():
    points = [(1, 3), (2, 2), (5, 4), (0, 1), (3, 0), (-1, 1)]
    k = 3
    nearest = heapq.nsmallest(k, points, key=score)
    print("nearest", nearest)

    best = []
    for point in points:
        value = score(point)
        if len(best) < k:
            heapq.heappush(best, (-value, point))
        elif value < -best[0][0]:
            q = heapq.heapreplace(best, (-value, point))
            print("dropped", q[1])
    kept = []
    while best:
        kept.append(heapq.heappop(best)[1])
    kept.reverse()
    print("kept", kept)

    far = heapq.nlargest(2, points, key=score)
    print("far", far)
    print("empty", heapq.nsmallest(4, []), heapq.nlargest(4, []))


main()
