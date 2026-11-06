def mix(a, b, n):
    i = 0
    while i < n:
        a[i] = b[i] * 2.0 + 0.5
        i += 1


def main():
    xs = [1.0, 2.0, 3.0]
    mix(xs, xs, 3)
    print(repr(xs[0]), repr(xs[1]), repr(xs[2]))


main()
