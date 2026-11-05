def put(xs, v):
    xs[0] = v


def main():
    a = [1, 2]
    put(a, 9223372036854775807)
    print(a)
    put(a, a[0] + 1)
    print(a)


main()
