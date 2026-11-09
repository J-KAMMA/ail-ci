"""All -0.0 with acc starting at -0.0: the chunk identity must keep the sign."""

def values():
    return [-0.0 for i in range(0, 100)]


START = -0.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
