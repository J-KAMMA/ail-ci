import heapq


def main():
    heap = []
    try:
        heapq.heappop(heap)
    except IndexError as exc:
        print("pop", type(exc).__name__, exc)
    try:
        heapq.heapreplace(heap, 1)
    except IndexError as exc:
        print("replace", type(exc).__name__, exc)

    print("pushpop", heapq.heappushpop(heap, 5), heap)
    heapq.heappush(heap, 4)
    heapq.heapify(heap)
    print("heap", heap)
    print("pop", heapq.heappop(heap), heap)

    heapq.heapify(heap)
    print("empty heapify", heap)
    print("largest", heapq.nlargest(3, []), heapq.nsmallest(2, []))
    print("over", heapq.nlargest(10, [2, 1]), heapq.nsmallest(10, [2, 1]))

    pairs = [(3, "c"), (1, "a"), (2, "b")]
    heapq.heapify(pairs)
    print("pairs", pairs)
    print("replace", heapq.heapreplace(pairs, (0, "z")), pairs)


main()
