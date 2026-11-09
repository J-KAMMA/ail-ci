"""acc starts from a non-zero value; two chunks (5000 items)."""

def values():
    return [i * 0.1 for i in range(0, 5000)]


START = 100.0


def main():
    xs = values()
    acc = START
    for i in par_range(0, len(xs)):
        acc += xs[i]
    print(repr(acc))


if __name__ == "__main__":
    main()
