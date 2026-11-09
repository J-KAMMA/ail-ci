"""Three items at 16 threads: more threads than items must not change the order."""

def values():
    return [1.5, 2.5, -4.0]


START = 0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
