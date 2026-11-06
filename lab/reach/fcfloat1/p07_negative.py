def last(xs, v):
    xs[-1] = v
    xs[-len(xs)] = v + 1.0


def bad(xs, v):
    xs[-10] = v


def main():
    xs = [1.0, 2.0, 3.0]
    last(xs, 9.5)
    print(repr(xs[0]), repr(xs[1]), repr(xs[2]))
    bad(xs, 1.0)
    print('unreachable')


main()
