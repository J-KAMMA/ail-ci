import heapq

heap: list[int] = [5, 1, 9, 3]
heapq.heapify(heap)
print("min", heap[0], "size", len(heap))
print("pop", heapq.heappop(heap), "now", heap)
empty: list[int] = []
print("empty", len(empty))
print(heapq.heappop(empty))
