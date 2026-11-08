"""Reference implementation of par_sum (see spec.md): sequential, reads N from stdin.

The sum is exact (Python ints); the int64 programs stop when a partial or the total leaves int64.
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
    total = 0
    for k in range(1, n + 1):
        total += steps(k) * (k % 7 - 3)
    return total


def main():
    data = sys.stdin.buffer.read().split()
    if len(data) != 1:
        return 1
    n = int(data[0])
    if n < 0:
        return 1
    sys.stdout.write('%d\n' % solve(n))
    return 0


if __name__ == '__main__':
    sys.exit(main())
