def grow(g):
    g[0].append(1.5)
    g.append([9.0])


def main():
    g = [[0.5], [2.0]]
    grow(g)
    print(len(g), len(g[0]), repr(g[0][1]), repr(g[2][0]))


main()
