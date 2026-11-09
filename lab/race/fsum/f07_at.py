"""n exactly at the chunk size: one full chunk of 4096 items."""

def values():
    return [1.0 / 3.0 for i in range(0, 4096)]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
