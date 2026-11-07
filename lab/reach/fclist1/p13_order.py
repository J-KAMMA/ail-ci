def bump(xs):
    xs[0] = xs[0] + 1
    return 100


def main():
    a = [1]
    x = a[0] + bump(a)
    y = bump(a) + a[0]
    print(x, y, a)
    print(a[0], bump(a), a[0])


main()
