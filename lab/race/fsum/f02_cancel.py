"""Cancellation: 1e16 + 1.0 loses the 1.0, then -1e16 leaves 0.0 in one chunk."""

def values():
    return [1e16, 1.0, -1e16]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
