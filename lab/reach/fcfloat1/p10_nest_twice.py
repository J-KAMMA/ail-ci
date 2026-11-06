def swap_into(g, h):
    g[0][0] = h[1][0]
    h[1][0] = -0.0


def main():
    g = [[1.5], [2.5]]
    swap_into(g, g)
    print(repr(g[0][0]), repr(g[1][0]))


main()
