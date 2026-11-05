import collections


def drain(dq: collections.deque[int]) -> int:
    return dq.pop()


dq: collections.deque[int] = collections.deque([1, 2])
dq.append(3)
print("deque", list(dq), "len", len(dq))
print("pop", drain(dq), "left", list(dq))
empty: collections.deque[int] = collections.deque()
print("empty", len(empty))
print(empty.pop())
