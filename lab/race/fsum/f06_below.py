"""n below the chunk size: one partial chunk of 4095 items."""

def values():
    return [1.0 / 3.0] * 4095


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
