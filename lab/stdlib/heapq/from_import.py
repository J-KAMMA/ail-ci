from heapq import heapify, heappop, heappush, heappushpop, heapreplace
from heapq import nlargest, nsmallest, merge


def summarize(values):
    heap = list(values)
    heapify(heap)
    out = []
    while heap:
        out.append(heappop(heap))
    return out


def main():
    numbers = [9, 4, 7, 1, 8, 2]
    print("sorted", summarize(numbers))
    print("original", numbers)
    print("top", nlargest(3, numbers), "bottom", nsmallest(3, numbers))

    heap = []
    for value in numbers:
        heappush(heap, value)
    print("peek", heap[0])
    print("swap", heapreplace(heap, 0), heappushpop(heap, 6))
    print("heap", heap)

    print("merge", list(merge([1, 4, 8], [2, 5], [3, 6, 7])))
    print("keys", list(merge([(2, "b")], [(1, "a")], key=lambda item: item[0])))


main()
