def keep(xs):
    xs[0] = 9
    return xs


def main():
    a = [1, 2]
    b = keep(a)
    print(b is a, a, b)


main()
