def setcell(g, i, j, v):
    g[i][j] = v


def main():
    g = [[0, 0, 0], [0, 0, 0]]
    setcell(g, 1, 2, 5)
    setcell(g, -1, 0, 9)
    print(g[1][2], g[1][0], g[0][0])


main()
