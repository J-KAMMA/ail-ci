def setc(g, v):
    g[0][0] = v


def main():
    g = [[1.0, 2.0], [3.0, 4.0]]
    g[1] = g[0]
    setc(g, 7.25)
    print(repr(g[1][0]), g[0] is g[1])


main()
