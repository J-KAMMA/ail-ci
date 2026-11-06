def clear(xs, n):
    i = 0
    while i < n:
        xs[i] = 0
        i += 1


def main():
    xs = [1.5, 2.5]
    clear(xs, 2)
    print(repr(xs[0]), repr(xs[1]))
    print(xs)


main()
