def first(g):
    r = g[0]
    return r[0]


def main():
    a = [[1.0, 2.0]]
    b = [[3, 4]]
    print(repr(first(a)), repr(first(b)))


main()
