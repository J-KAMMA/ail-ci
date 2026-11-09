"""NaN flows through the sum (one chunk, NaN is absorbing)."""

def values():
    big = 1e308
    inf = big * big
    nan = inf - inf
    return [1.0, nan, 2.0, inf, -inf]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
