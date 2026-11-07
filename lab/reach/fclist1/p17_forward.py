def inner(xs, i, v):
    xs[i] = v


def outer(xs, ys, n):
    i = 0
    while i < n:
        inner(xs, i, ys[i] * 2)
        i += 1


def main():
    a = [0] * 4
    b = [1, 2, 3, 4]
    outer(a, b, 4)
    outer(b, b, 4)
    print(a, b)


main()
