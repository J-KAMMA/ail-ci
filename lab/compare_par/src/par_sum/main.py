import sys
from concurrent.futures import ThreadPoolExecutor


def steps(n: int) -> int:
    c = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        c += 1
    return c


def term(n: int) -> int:
    return steps(n) * (n % 7 - 3)


def main() -> int:
    data = sys.stdin.buffer.read().split()
    if len(data) != 1:
        return 1
    n = int(data[0])
    with ThreadPoolExecutor(max_workers=4) as ex:
        total = sum(ex.map(term, range(1, n + 1)))
    sys.stdout.write('%d\n' % total)
    return 0


if __name__ == '__main__':
    sys.exit(main())
