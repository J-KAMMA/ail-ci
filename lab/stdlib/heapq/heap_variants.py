import heapq


def drain(heap):
    out = []
    while heap:
        out.append(heapq.heappop(heap))
    return out


def main():
    floats = [2.5, 0.5, 1.5, 3.5, 0.25]
    heapq.heapify(floats)
    print("float", drain(floats))

    words = ["pear", "apple", "fig", "kiwi", "date"]
    heapq.heapify(words)
    print("words", drain(words))

    mixed = [(2, "b"), (1, "z"), (2, "a"), (1, "a")]
    heapq.heapify(mixed)
    print("tuples", drain(mixed))

    heap = [4, 2, 9]
    heapq.heapify(heap)
    print("first", heap[0])
    print("pushpop", heapq.heappushpop(heap, 0), heap)
    print("replace", heapq.heapreplace(heap, 10), heap)
    print("drain", drain(heap))
    print("empty", drain([]))


main()
