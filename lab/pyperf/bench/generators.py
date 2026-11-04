"""Generators: a pipeline of generator functions over a large range.

The source yields integers, a filter drops multiples of three, a mixer keeps
only every other value after scaling, and the consumer sums the first n of
them.  A recursive tree walk feeds a second generator chain.  Printing is
integer only.
"""
import sys


def counter(n):
    i = 0
    while i < n:
        yield i
        i += 1


def keep(seq, m):
    for v in seq:
        if v % m != 0:
            yield v


def mix(seq, k):
    i = 0
    for v in seq:
        if i % 2 == 0:
            yield v * k + (v >> 2)
        i += 1


def tree(depth, fan):
    if depth == 0:
        yield 1
        return
    i = 0
    while i < fan:
        for leaf in tree(depth - 1, fan):
            yield leaf + i
        i += 1


def total(seq, limit):
    seen = 0
    out = 0
    for v in seq:
        if seen >= limit:
            break
        out += v
        seen += 1
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20000000
    a = total(mix(keep(counter(n), 3), 5), n)
    b = total(tree(6, 4), n)
    print(a)
    print(b)


main()
