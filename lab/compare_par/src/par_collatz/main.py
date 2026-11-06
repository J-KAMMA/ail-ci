import sys
from concurrent.futures import ThreadPoolExecutor


def steps(n: int) -> int:
    c = 0
    while n != 1:
        if n & 1:
            n = 3 * n + 1
        else:
            n >>= 1
        c += 1
    return c


def main() -> int:
    data = sys.stdin.buffer.read().split()
    if len(data) != 2:
        return 1
    n = int(data[0])
    w = int(data[1])
    with ThreadPoolExecutor(max_workers=w) as ex:
        res = list(ex.map(steps, range(1, n + 1)))
    best = -1
    bestn = 0
    total = 0
    for i in range(n):
        v = res[i]
        total += v
        if v > best:
            best = v
            bestn = i + 1
    sys.stdout.write('%d %d %d\n' % (best, bestn, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
