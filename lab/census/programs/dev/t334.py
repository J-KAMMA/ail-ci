from collections import deque
import sys


def main() -> None:
    data = sys.stdin.read().split()
    if not data:
        print(0)
        return

    n = int(data[0])
    t = int(data[1])
    values = [int(x) for x in data[2:2 + n]]
    n = len(values)

    prefix = [0] * (n + 1)
    for i, v in enumerate(values):
        prefix[i + 1] = prefix[i] + v

    best = float("inf")
    dq: deque[int] = deque()

    for j in range(n + 1):
        while dq and prefix[j] - prefix[dq[0]] >= t:
            best = min(best, j - dq.popleft())
        while dq and prefix[dq[-1]] >= prefix[j]:
            dq.pop()
        dq.append(j)

    print(0 if best == float("inf") else int(best))


if __name__ == "__main__":
    main()
