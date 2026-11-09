"""Infinity flows through the sum (one chunk)."""

def values():
    big = 1e308
    inf = big * big
    return [1.0, inf, 2.0]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
