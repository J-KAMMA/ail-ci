"""Reference implementation of par_collatz (see spec.md): sequential, reads N and W from stdin.

W is read and ignored: the worker count never changes the result.
"""
import sys


def steps(n):
    c = 0
    while n != 1:
        if n & 1:
            n = 3 * n + 1
        else:
            n >>= 1
        c += 1
    return c


def solve(n):
    best = -1
    bestn = 0
    total = 0
    for k in range(1, n + 1):
        v = steps(k)
        total += v
        if v > best:
            best = v
            bestn = k
    return best, bestn, total


def main():
    data = sys.stdin.buffer.read().split()
    if len(data) != 2:
        return 1
    n, _w = int(data[0]), int(data[1])
    best, bestn, total = solve(n)
    sys.stdout.write('%d %d %d\n' % (best, bestn, total))
    return 0


if __name__ == '__main__':
    sys.exit(main())
