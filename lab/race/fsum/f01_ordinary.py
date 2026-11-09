"""Ordinary values over eight chunks (10000 items); catches any chunk-order dependence."""

def values():
    return [i * 0.5 for i in range(0, 10000)]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
