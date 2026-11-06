def f(g):
    g = [[0.0]]
    g[0][0] = 1.0
    return g[0][0]


def main():
    g = [[5.0]]
    print(repr(f(g)), repr(g[0][0]))


main()
