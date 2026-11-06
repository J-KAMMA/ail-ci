def bump(xs):
    xs[0] = xs[0] + 1.0
    return xs[0]


def main():
    a = [1.0]
    t = a[0] + bump(a)
    print(repr(t), repr(a[0]))


main()
