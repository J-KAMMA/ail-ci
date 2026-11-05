def setv(xs, v):
    xs[0] = v


def main():
    a = [1, 2]
    b = a
    setv(a, 42)
    print(a, b)


main()
