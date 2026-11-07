def setv(xs, v):
    xs[0] = v


def main():
    a = [1, 2]
    rows = [a, [3, 4]]
    setv(a, 42)
    print(rows, a)


main()
