def bump(g, n):
    i = 0
    while i < n:
        r = g[i]
        r[1] = r[1] + 0.5
        i += 1


def main():
    g = [[1.0, 2.0], [3.0, 4.0]]
    bump(g, 2)
    print(repr(g[0][1]), repr(g[1][1]))
    print(g)


main()
