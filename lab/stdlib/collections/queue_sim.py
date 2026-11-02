from collections import deque


def drain(q: deque[str]) -> None:
    while q:
        print("serve", q.popleft())


def main() -> int:
    q: deque[str] = deque()
    print(len(q), bool(q))
    q.append("a")
    q.append("b")
    q.appendleft("front")
    print(list(q), q[0], q[-1])
    print(q.popleft(), q.pop())
    print(list(q))
    drain(q)
    print(list(q))
    try:
        q.popleft()
    except IndexError as exc:
        print("IndexError", exc)
    try:
        q.pop()
    except IndexError as exc:
        print("IndexError", exc)
    q.extend(["x", "y", "x"])
    try:
        q.remove("x")
        print(list(q))
        q.remove("missing")
    except ValueError as exc:
        print("ValueError", exc)
    try:
        print(q.index("missing"))
    except ValueError as exc:
        print("ValueError", exc)
    limited: deque[int] = deque([1, 2, 3], maxlen=2)
    print(list(limited))
    limited.appendleft(9)
    print(list(limited))
    zero: deque[int] = deque(maxlen=0)
    zero.append(1)
    print(list(zero), len(zero))
    again = deque(limited)
    again.reverse()
    print(list(again))
    q.extendleft(["1", "2"])
    print(list(q))
    return 0


main()
