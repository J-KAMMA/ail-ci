def setc(g, v):
    g[0][0] = v


def main():
    g = [[1.5, 2.5]]
    setc(g, 3)
    print(repr(g[0][0]))
    print(g)


main()
