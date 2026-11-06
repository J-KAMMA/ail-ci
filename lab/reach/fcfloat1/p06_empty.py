def scale(xs, k):
    i = 0
    while i < len(xs):
        xs[i] = xs[i] * k
        i += 1


def main():
    xs = [2.5]
    xs.pop()
    scale(xs, 2.0)
    print(len(xs))
    ys = [1.25, 3.0]
    scale(ys, 2.0)
    print(repr(ys[0]), repr(ys[1]))


main()
