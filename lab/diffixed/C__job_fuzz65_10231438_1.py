# C?-job-fuzz65-10231438-1: annotated list repr after a caught heappush TypeError
import heapq

xs: list[int] = [1]
try:
    heapq.heappush(xs, "x")
except TypeError as exc:
    print(type(exc).__name__)
print(xs)
print(repr(xs))

pairs: list[tuple[int, str]] = [(1, "a"), (2, "b")]
try:
    heapq.heappush(pairs, "z")
except TypeError as exc:
    print(type(exc).__name__)
print(pairs)
print(repr(pairs))

ys: list[int] = [3, 1]
heapq.heapify(ys)
try:
    heapq.heappush(ys, None)
except TypeError as exc:
    print(type(exc).__name__)
print(ys)
