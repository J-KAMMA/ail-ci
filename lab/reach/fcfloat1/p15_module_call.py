def setc(g, v):
    g[0][0] = v


def main():
    g = [[1.0]]
    setc(g, 2.0)
    print(repr(g[0][0]))


main()
h = [[3.0]]
setc(h, 4.0)
print(repr(h[0][0]))
