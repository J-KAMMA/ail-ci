from collections import deque


def moving_average(values: list[int], width: int) -> list[float]:
    window: deque[int] = deque(maxlen=width)
    result = []
    total = 0
    for value in values:
        if len(window) == width:
            total -= window.popleft()
        window.append(value)
        total += value
        if len(window) == width:
            result.append(total / width)
    return result


def window_max(values: list[int], width: int) -> list[int]:
    window: deque[int] = deque()
    best = []
    for i, value in enumerate(values):
        while window and window[-1] < value:
            window.pop()
        window.append(value)
        if i >= width and window[0] == values[i - width]:
            window.popleft()
        if i >= width - 1:
            best.append(window[0])
    return best


def main() -> int:
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5]
    print(moving_average(data, 3))
    print(window_max(data, 3))
    q: deque[int] = deque([1, 2, 3])
    q.appendleft(0)
    q.append(4)
    q.rotate(2)
    print(list(q), len(q), q[0], q[-1])
    q.rotate(-1)
    q.extend([5, 6])
    q.extendleft([-1, -2])
    print(list(q))
    print(q.index(3), q.count(3))
    q.remove(4)
    print(list(q))
    q.clear()
    print(list(q), len(q), bool(q))
    capped: deque[int] = deque([1, 2], maxlen=3)
    for value in [3, 4, 5]:
        capped.append(value)
        print(list(capped))
    return 0


main()
